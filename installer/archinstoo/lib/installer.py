import os
import re
import shlex
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess
from typing import TYPE_CHECKING, Self

from archinstoo.lib.bootloader.install import BootloaderInstaller, configure_grub_btrfsd
from archinstoo.lib.disk.cleanup import teardown_layout
from archinstoo.lib.disk.cryptenroll import enroll_fido2, enroll_tpm2
from archinstoo.lib.disk.device_handler import DeviceHandler
from archinstoo.lib.disk.luks import Luks2, unlock_luks2_dev
from archinstoo.lib.disk.lvm import lvm_import_vg, lvm_vol_change
from archinstoo.lib.disk.utils import mount, swapon
from archinstoo.lib.exceptions import DiskError, HardwareIncompatibilityError, RequirementError, ServiceError, SysCallError
from archinstoo.lib.general import SysCommand, run
from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.linux_path import LPath
from archinstoo.lib.localization.utils import locale_encoding, split_locale_name, uncomment_locale
from archinstoo.lib.models.authentication import PrivilegeEscalation
from archinstoo.lib.models.bootloader import Bootloader
from archinstoo.lib.models.device import (
	BOOT_ITER_TIME,
	BOOT_PBKDF_MEMORY,
	DiskEncryption,
	DiskLayoutConfiguration,
	EncryptionType,
	FilesystemType,
	LvmVolume,
	PartitionModification,
	SnapshotType,
	SubvolumeModification,
	harden_boot_options,
)
from archinstoo.lib.models.firmware import FirmwareConfiguration
from archinstoo.lib.models.kernel import DEFAULT_KERNEL
from archinstoo.lib.models.network import ISO_PSK_EXTRA
from archinstoo.lib.models.swap import SwapConfiguration, ZramAlgorithm
from archinstoo.lib.models.users import User
from archinstoo.lib.output import debug, error, info, log, logger, warn
from archinstoo.lib.pathnames import ARTIFACTS_STORE, MIRRORLIST
from archinstoo.lib.pm import Pacman
from archinstoo.lib.pm.config import PacmanConfig
from archinstoo.lib.pm.mirrors import MirrorListHandler
from archinstoo.lib.systemd import accessibility_tools_in_use, wait_iso_services
from archinstoo.lib.utils.env import Os

if TYPE_CHECKING:
	from collections.abc import Callable
	from types import TracebackType

	from archinstoo.lib.args import ArchConfigHandler
	from archinstoo.lib.models.locale import LocaleConfiguration
	from archinstoo.lib.models.mirrors import PacmanConfiguration
	from archinstoo.lib.models.network import Nic
	from archinstoo.lib.models.packages import Repository
	from archinstoo.lib.models.service import UserService

# Base packages installed by default (firmware added based on FirmwareConfiguration)
# mkinitcpio is listed explicitly so pacstrap installs it deterministically. Otherwise
# pacman picks the first initramfs provider from the host's pacman.conf, which on non-Arch
# hosts (EndeavourOS prefers dracut, etc.) breaks the installer's mkinitcpio() and
# _config_uki() methods that assume mkinitcpio is present in the chroot.
__base_packages__ = ['base', 'mkinitcpio']

# Package sets minimal_installation() and the steps after it add conditionally.
# Named rather than inlined so schema_gen can read the same list the installer
# straps, instead of a transcription of it.
LVM = 'lvm2'  # package and mkinitcpio hook share the name
__lvm_packages__ = [LVM]
# out-of-tree module, built per kernel: every selected kernel also pulls -headers
__bcachefs_packages__ = ['bcachefs-dkms']
# sd-encrypt only bundles the fido2 dlopen libs if this is present when the
# initramfs is built
__fido2_packages__ = ['libfido2']
# fonts that are in the ISO but wont be on target unless requested before base,
# otherwise mkinitcpio will be screaming at you
__ter_font_packages__ = ['terminus-font']
# grub integration for either snapshot tool
__grub_snapshot_packages__ = ['grub-btrfs', 'inotify-tools']
__zram_packages__ = ['zram-generator']
# cloning a user stash
__stash_packages__ = ['git']

# Additional packages that are installed if the user is running the Live ISO with accessibility tools enabled
__accessibility_packages__ = ['brltty', 'espeakup', 'alsa-utils']


class Installer:
	def __init__(
		self,
		target: Path,
		disk_config: DiskLayoutConfiguration,
		base_packages: list[str] | None = None,
		kernels: list[str] | None = None,
		firmware: FirmwareConfiguration | None = None,
		*,
		handler: ArchConfigHandler | None = None,
		device_handler: DeviceHandler | None = None,
	) -> None:
		# `Installer()` is the wrapper for most basic installation steps.
		# It also wraps :py:func:`~archinstoo.Installer.pacstrap` among other things.
		from archinstoo.lib.args import Arguments

		self._handler = handler
		# lazy: constructing DeviceHandler scans disks and needs pyparted,
		# neither wanted for no-disk-ops runs (live)
		self._device_handler = device_handler
		self._args = handler.args if handler else Arguments()
		self._bug_report_url = handler.config.bug_report_url if handler else 'https://github.com/h8d13/archinstoo/issues'

		self._base_packages = list(base_packages or __base_packages__)
		self._base_packages.extend((firmware or FirmwareConfiguration()).packages())
		self.kernels = kernels or [DEFAULT_KERNEL.value]
		self._disk_config = disk_config

		self._disk_encryption = disk_config.disk_encryption or DiskEncryption(EncryptionType.NO_ENCRYPTION)
		self.target: Path = target

		self._helper_flags: dict[str, str | bool | None] = {
			'base': False,
			'bootloader': None,
		}

		for kernel in self.kernels:
			self._base_packages.append(kernel)

		# If using accessibility tools in the live environment, append those to the packages list
		if accessibility_tools_in_use():
			self._base_packages.extend(__accessibility_packages__)

		self.post_base_install: list[Callable[[], None]] = []

		self._modules: list[str] = []
		self._binaries: list[str] = []
		self._files: list[str] = []

		# sd-encrypt is inserted by _prepare_encrypt() when disk encryption is configured
		self._hooks: list[str] = [
			'base',
			'systemd',
			'autodetect',
			'microcode',
			'modconf',
			'kms',
			'keyboard',
			'sd-vconsole',
			'block',
			'filesystems',
			'fsck',
		]
		self._kernel_params: list[str] = []
		self._fstab_entries: list[str] = []

		self._zram_enabled = False
		self._disable_fstrim = False
		self._layout_teardown_required = False

		self.pacman = Pacman(self.target)

	@property
	def handler(self) -> ArchConfigHandler | None:
		return self._handler

	@property
	def device_handler(self) -> DeviceHandler:
		if self._device_handler is None:
			self._device_handler = DeviceHandler()
		return self._device_handler

	def set_helper_flag(self, key: str, value: str | bool | None) -> None:
		self._helper_flags[key] = value

	def __enter__(self) -> Self:
		return self

	def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool | None:
		try:
			if exc_type is KeyboardInterrupt:
				# User abort, not a crash: no bug-report prompt. finally still
				# tears down mounts; propagate for the top level to exit clean.
				warn('Installation interrupted by user, tearing down target...')
				return None

			if exc_type is not None:
				error(str(exc_value))
				info(f'[!] A log file has been created here: {logger.path}')
				info(f'Please submit this issue (and file) to {self._bug_report_url}/issues')

				# Return None to propagate the exception
				return None

			info('Syncing the system...')
			os.sync()

			if not (missing_steps := self.post_install_check()):
				# live/packages install onto the running system: the changes are
				# already in effect, there is nothing to reboot into
				closing = 'Changes are live on the running system.' if self.target == Path('/') else 'You may reboot when ready.'
				msg = (
					'Installation completed without any errors.\n'
					f'Log files available at {logger.directory} and in target {ARTIFACTS_STORE}.\n'
					f'{closing}\n'
				)
				log(msg, fg='green')

				return True
			warn('Some required steps were not successfully installed/configured before leaving the installer:')

			for step in missing_steps:
				warn(f' - {step}')

			warn(f'Detailed error logs can be found at: {logger.directory}')
			warn(f'Please submit this issue to {self._bug_report_url}/issues')

			return False
		finally:
			try:
				self._teardown_target()
			except Exception as err:
				warn(f'Failed to teardown installation target: {err}')

	def sync_artifacts_to_target(self) -> None:
		# Copy the run log and saved user config into the target so they survive reboot
		# at /etc/archinstoo.d/<timestamp>_{install.log,config.json} for post-install debugging.
		try:
			dest_dir = self.target / ARTIFACTS_STORE.relative_to_root()
			dest_dir.mkdir(mode=0o755, exist_ok=True)

			ts = datetime.now(tz=UTC).strftime('%Y-%m-%dT%H-%M')
			artifacts = [
				(logger.path, f'{ts}_install.log'),
				(logger.directory / 'user_configuration.json', f'{ts}_config.json'),
			]

			for src, dst_name in artifacts:
				if src.exists():
					dst = dest_dir / dst_name
					src.copy(dst, preserve_metadata=True)
					dst.chmod(0o640)
		except Exception as e:
			warn(f'Failed to sync install artifacts to target: {e}')

	def _teardown_target(self) -> None:
		if not self._layout_teardown_required:
			debug('No mounted layout registered for teardown')
			return

		teardown_layout(
			self.target,
			self._disk_config,
			self._disk_encryption,
			self.device_handler,
		)
		self._layout_teardown_required = False

	def sanity_check(self) -> None:
		wait_iso_services(self._args.skip_ntp, self._args.skip_wkd)

	def mount_ordered_layout(self) -> None:
		info(f'Mounting ordered layout at {self.target} (encryption: {self._disk_encryption.encryption_type.value})', step=True)
		self._layout_teardown_required = True

		luks_handlers: dict[PartitionModification | LvmVolume, Luks2] = {}

		match self._disk_encryption.encryption_type:
			case EncryptionType.NO_ENCRYPTION:
				self._import_lvm()
				self._mount_lvm_layout()
			case EncryptionType.LUKS:
				luks_handlers = self._prepare_luks_partitions(self._disk_encryption.partitions)
			case EncryptionType.LVM_ON_LUKS:
				luks_handlers = self._prepare_luks_partitions(self._disk_encryption.partitions)
				self._import_lvm()
				self._mount_lvm_layout(luks_handlers)
			case EncryptionType.LUKS_ON_LVM:
				self._import_lvm()
				luks_handlers = self._prepare_luks_lvm(self._disk_encryption.lvm_volumes)
				self._mount_lvm_layout(luks_handlers)

		# mount all regular partitions
		self._mount_partition_layout(luks_handlers)

	def _mount_partition_layout(self, luks_handlers: dict[PartitionModification | LvmVolume, Luks2]) -> None:
		debug('Mounting partition layout')

		# do not mount any PVs part of the LVM configuration
		pvs = []
		if self._disk_config.lvm_config:
			pvs = self._disk_config.lvm_config.get_all_pvs()

		sorted_device_mods = self._disk_config.device_modifications.copy()

		# move the device with the root partition to the beginning of the list
		for mod in self._disk_config.device_modifications:
			if any(partition.is_root() for partition in mod.partitions):
				sorted_device_mods.remove(mod)
				sorted_device_mods.insert(0, mod)
				break

		for mod in sorted_device_mods:
			not_pv_part_mods = [p for p in mod.partitions if p not in pvs]

			# partitions have to mounted in the right order on btrfs the mountpoint will
			# be empty as the actual subvolumes are getting mounted instead so we'll use
			# '/' just for sorting
			sorted_part_mods = sorted(not_pv_part_mods, key=lambda x: x.mountpoint or Path('/'))

			for part_mod in sorted_part_mods:
				if luks_handler := luks_handlers.get(part_mod):
					self._mount_luks_partition(part_mod, luks_handler)
				else:
					self._mount_partition(part_mod)

	def _mount_lvm_layout(self, luks_handlers: dict[PartitionModification | LvmVolume, Luks2] | None = None) -> None:
		if luks_handlers is None:
			luks_handlers = {}

		lvm_config = self._disk_config.lvm_config

		if not lvm_config:
			debug('No lvm config defined to be mounted')
			return

		debug('Mounting LVM layout')

		for vg in lvm_config.vol_groups:
			sorted_vol = sorted(vg.volumes, key=lambda x: x.mountpoint or Path('/'))

			for vol in sorted_vol:
				if luks_handler := luks_handlers.get(vol):
					self._mount_luks_volume(vol, luks_handler)
				else:
					self._mount_lvm_vol(vol)

	def _prepare_luks_partitions(
		self,
		partitions: list[PartitionModification],
	) -> dict[PartitionModification | LvmVolume, Luks2]:
		return {
			part_mod: unlock_luks2_dev(
				part_mod.dev_path,
				part_mod.mapper_name,
				self._disk_encryption.encryption_password,
			)
			for part_mod in partitions
			if part_mod.mapper_name and part_mod.dev_path
		}

	def _import_lvm(self) -> None:
		lvm_config = self._disk_config.lvm_config

		if not lvm_config:
			debug('No lvm config defined to be imported')
			return

		for vg in lvm_config.vol_groups:
			lvm_import_vg(vg)

			for vol in vg.volumes:
				lvm_vol_change(vol, True)

	def _prepare_luks_lvm(
		self,
		lvm_volumes: list[LvmVolume],
	) -> dict[PartitionModification | LvmVolume, Luks2]:
		return {
			vol: unlock_luks2_dev(
				vol.dev_path,
				vol.mapper_name,
				self._disk_encryption.encryption_password,
			)
			for vol in lvm_volumes
			if vol.mapper_name and vol.dev_path
		}

	# src/shared/dissect-image.c. FAT has no on-disk perms, hence the masks
	def _mount_partition(self, part_mod: PartitionModification) -> None:
		if not part_mod.dev_path:
			debug(f'Partition {part_mod.mountpoint or part_mod.fs_type} has no device path, skipping mount')
			return

		# subvolumes carry their own mountpoints and win over the partition's, which
		# a manual layout can still set: mounting that would put the install on the
		# top-level subvolume and leave every subvolume created but unused
		if part_mod.fs_type == FilesystemType.BTRFS and part_mod.btrfs_subvols:
			if self._has_mountable_subvols(part_mod.dev_path, part_mod.btrfs_subvols):
				self._mount_btrfs_subvol(
					part_mod.dev_path,
					part_mod.btrfs_subvols,
					part_mod.mount_options,
				)
		elif part_mod.mountpoint:
			target = self.target / part_mod.relative_mountpoint
			mount_fs = part_mod.fs_type.fs_type_mount if part_mod.fs_type else None
			options = harden_boot_options(part_mod, list(part_mod.mount_options))

			mount(part_mod.dev_path, target, mount_fs=mount_fs, options=options)
		elif part_mod.is_swap():
			swapon(part_mod.dev_path)

	def _mount_lvm_vol(self, volume: LvmVolume) -> None:
		if volume.fs_type != FilesystemType.BTRFS and volume.mountpoint and volume.dev_path:
			target = self.target / volume.relative_mountpoint
			mount(volume.dev_path, target, mount_fs=volume.fs_type.fs_type_mount, options=volume.mount_options)

		if volume.fs_type == FilesystemType.BTRFS and volume.dev_path and self._has_mountable_subvols(volume.dev_path, volume.btrfs_subvols):
			self._mount_btrfs_subvol(volume.dev_path, volume.btrfs_subvols, volume.mount_options)

	def _mount_luks_partition(self, part_mod: PartitionModification, luks_handler: Luks2) -> None:
		if not luks_handler.mapper_dev:
			return

		if part_mod.fs_type == FilesystemType.BTRFS and part_mod.btrfs_subvols:
			if self._has_mountable_subvols(luks_handler.mapper_dev, part_mod.btrfs_subvols):
				self._mount_btrfs_subvol(luks_handler.mapper_dev, part_mod.btrfs_subvols, part_mod.mount_options)
		elif part_mod.is_swap():
			swapon(luks_handler.mapper_dev)
			self._fstab_entries.append(f'{luks_handler.mapper_dev}\tnone\tswap\tdefaults\t0\t0')
		elif part_mod.mountpoint:
			target = self.target / part_mod.relative_mountpoint
			mount_fs = part_mod.fs_type.fs_type_mount if part_mod.fs_type else None
			# encrypted /boot (GRUB) needs the same hardening as a plain one
			options = harden_boot_options(part_mod, list(part_mod.mount_options))
			mount(luks_handler.mapper_dev, target, mount_fs=mount_fs, options=options)

	def _mount_luks_volume(self, volume: LvmVolume, luks_handler: Luks2) -> None:
		mapper = luks_handler.mapper_dev

		if volume.fs_type != FilesystemType.BTRFS and volume.mountpoint and mapper:
			target = self.target / volume.relative_mountpoint
			mount(mapper, target, mount_fs=volume.fs_type.fs_type_mount, options=volume.mount_options)

		if volume.fs_type == FilesystemType.BTRFS and mapper and self._has_mountable_subvols(mapper, volume.btrfs_subvols):
			self._mount_btrfs_subvol(mapper, volume.btrfs_subvols, volume.mount_options)

	def _has_mountable_subvols(self, dev_path: Path, subvolumes: list[SubvolumeModification]) -> bool:
		# only subvolumes with a mountpoint get mounted, and the partition must
		# not stand in for them: an empty set means nothing lands here
		if any(sv.mountpoint is not None for sv in subvolumes):
			return True

		warn(f'{dev_path}: no btrfs subvolume with a mountpoint, nothing mounted there')
		return False

	def _mount_btrfs_subvol(
		self,
		dev_path: Path,
		subvolumes: list[SubvolumeModification],
		mount_options: list[str] | None = None,
	) -> None:
		if mount_options is None:
			mount_options = []

		# Filter out subvolumes without mountpoints to avoid errors when sorting
		subvols_with_mountpoints = [sv for sv in subvolumes if sv.mountpoint is not None]
		for subvol in sorted(subvols_with_mountpoints, key=lambda x: x.relative_mountpoint):
			mountpoint = self.target / subvol.relative_mountpoint
			options = [*mount_options, f'subvol={subvol.name}']
			mount(dev_path, mountpoint, mount_fs='btrfs', options=options)

	def generate_key_files(self) -> None:
		info(f'Generating key files for {self._disk_encryption.encryption_type.value}...')
		match self._disk_encryption.encryption_type:
			case EncryptionType.LUKS:
				self._generate_key_files_partitions()
			case EncryptionType.LUKS_ON_LVM:
				self._generate_key_file_lvm_volumes()
			case EncryptionType.NO_ENCRYPTION:
				pass
			case EncryptionType.LVM_ON_LUKS:
				# LvmOnLuks: the LUKS container holds an LVM PV, root is a volume inside it.
				# The partition itself isn't "root", so _generate_key_files_partitions
				# can't detect it via is_root(). Handle it directly here.
				if self._disk_encryption.auto_unlock_root:
					for part_mod in self._disk_encryption.partitions:
						if part_mod.is_boot() or part_mod.is_efi():
							continue
						luks_handler = Luks2(
							part_mod.safe_dev_path,
							mapper_name=part_mod.mapper_name,
							password=self._disk_encryption.encryption_password,
						)
						self._create_root_keyfile(luks_handler, mapper_name='cryptlvm')
						break

	def _generate_key_files_partitions(self) -> None:
		root_is_encrypted = any(p.is_root() for p in self._disk_encryption.partitions)

		for part_mod in self._disk_encryption.partitions:
			gen_enc_file = self._disk_encryption.should_generate_encryption_file(part_mod)

			luks_handler = Luks2(
				part_mod.safe_dev_path,
				mapper_name=part_mod.mapper_name,
				password=self._disk_encryption.encryption_password,
			)

			if gen_enc_file and not part_mod.is_root():
				debug(f'Creating key-file: {part_mod.dev_path}')
				if root_is_encrypted and not part_mod.luks_mapper:  # pre-opened: no passphrase to derive from
					# GRUB has limited memory for argon2 decryption;
					# constrain the keyfile slot too so GRUB can handle it
					is_boot = part_mod.is_boot()
					uses_argon2 = self._disk_encryption.pbkdf.is_argon2
					pbkdf_memory = BOOT_PBKDF_MEMORY if is_boot and uses_argon2 else None
					iter_time = BOOT_ITER_TIME if is_boot else self._disk_encryption.iter_time
					luks_handler.create_keyfile(
						self.target,
						pbkdf_memory=pbkdf_memory,
						iter_time=iter_time,
						pbkdf=self._disk_encryption.pbkdf,
					)
				else:
					# unencrypted root (keyfile would sit in plaintext) or pre-opened: prompt via crypttab
					luks_handler.create_crypttab_entry(self.target)

			if self._disk_encryption.auto_unlock_root and part_mod.is_root():
				self._create_root_keyfile(luks_handler)

	def _generate_key_file_lvm_volumes(self) -> None:
		root_is_encrypted = any(v.is_root() for v in self._disk_encryption.lvm_volumes)

		for vol in self._disk_encryption.lvm_volumes:
			gen_enc_file = self._disk_encryption.should_generate_encryption_file(vol)

			luks_handler = Luks2(
				vol.safe_dev_path,
				mapper_name=vol.mapper_name,
				password=self._disk_encryption.encryption_password,
			)

			if gen_enc_file and not vol.is_root():
				debug(f'Creating key-file: {vol.dev_path}')
				if root_is_encrypted:
					luks_handler.create_keyfile(
						self.target,
						iter_time=self._disk_encryption.iter_time,
						pbkdf=self._disk_encryption.pbkdf,
					)
				else:
					luks_handler.create_crypttab_entry(self.target)

			if self._disk_encryption.auto_unlock_root and vol.is_root():
				self._create_root_keyfile(luks_handler)

	def _create_root_keyfile(self, luks_handler: Luks2, mapper_name: str = 'root') -> None:
		# sd-encrypt standard path and add it as a LUKS
		# key slot so the volume can be auto-unlocked from the initramfs.
		# sd-encrypt auto-detects keys at /etc/cryptsetup-keys.d/<name>.key.
		kf_path = f'/etc/cryptsetup-keys.d/{mapper_name}.key'
		keyfile = self.target / kf_path.lstrip('/')

		debug(f'Creating key-file: {keyfile}')
		keyfile.parent.mkdir(parents=True, exist_ok=True)
		keyfile.write_bytes(os.urandom(2048))
		keyfile.chmod(0o000)

		# initramfs unlocks this slot on the host CPU, user's iter_time applies
		luks_handler.add_key(
			keyfile,
			iter_time=self._disk_encryption.iter_time,
			pbkdf=self._disk_encryption.pbkdf,
		)

		if kf_path not in self._files:
			self._files.append(kf_path)

	def post_install_check(self) -> list[str]:
		return [step for step, flag in self._helper_flags.items() if flag is False]

	def set_mirrors(
		self,
		pacman_configuration: PacmanConfiguration,
		on_target: bool = False,
	) -> None:
		# Set the mirror configuration for the installation.
		#
		# :param pacman_configuration: The pacman configuration to use.
		# :type pacman_configuration: PacmanConfiguration
		#
		# :on_target: Whether to set the mirrors on the target system or the live system.
		# :param on_target: bool
		info('Setting mirrors on ' + ('target' if on_target else 'live system' + '...'))

		mirrorlist_path = self.target / MIRRORLIST.relative_to_root() if on_target else MIRRORLIST

		# repos, custom repos, misc options and ParallelDownloads all land in
		# the conf for this side of the install
		PacmanConfig.apply_config(pacman_configuration, self.target if on_target else None)

		# Speed test only for the live system, target reuses the same order
		regions_config = MirrorListHandler().regions_config(pacman_configuration.mirror_regions, speed_sort=not on_target)
		if regions_config:
			debug(f'Mirrorlist:\n{regions_config}')
			mirrorlist_path.write_text(regions_config)

		if custom_servers := pacman_configuration.custom_servers_config():
			debug(f'Custom servers:\n{custom_servers}')

			content = mirrorlist_path.read_text()
			mirrorlist_path.write_text(f'{custom_servers}\n\n{content}')

	def genfstab(self, flags: str = '-pU') -> None:
		fstab_path = self.target / 'etc' / 'fstab'
		info(f'Generating {fstab_path}', step=True)
		try:
			gen_fstab = SysCommand(f'genfstab {flags} -f {self.target} {self.target}').output()
		except SysCallError as err:
			raise RequirementError(
				f'Could not generate fstab, strapping in packages most likely failed (disk out of space?)\n Error: {err}'
			) from err

		with fstab_path.open('ab') as fp:
			fp.write(gen_fstab)

		if not fstab_path.is_file():
			raise RequirementError('Could not create fstab file')

		with fstab_path.open('a') as fp:
			fp.writelines(f'{entry}\n' for entry in self._fstab_entries)

	def set_hostname(self, hostname: str) -> None:
		(self.target / 'etc/hostname').write_text(hostname + '\n')
		debug(f'Wrote hostname {hostname}')

	def set_locale(self, locale_config: LocaleConfiguration) -> bool:
		# the menu keeps language and encoding apart; locale.gen names them
		# together, so the same splitting the encoding menu scopes itself by
		lang, _, modifier = split_locale_name(locale_config.sys_lang)
		encoding = locale_encoding(locale_config.sys_lang, locale_config.sys_enc)

		locale_gen = self.target / 'etc/locale.gen'
		locale_gen_lines = locale_gen.read_text().splitlines(True)

		if not uncomment_locale(locale_gen_lines, locale_config.sys_lang, locale_config.sys_enc):
			error(f"Invalid locale: language '{locale_config.sys_lang}', encoding '{locale_config.sys_enc}'")
			return False
		# tools hardcoding LC_ALL=en_US.UTF-8 warn on every non-US system otherwise
		# https://github.com/archlinux/archinstall/issues/3764
		uncomment_locale(locale_gen_lines, 'en_US.UTF-8', 'UTF-8')
		locale_gen.write_text(''.join(locale_gen_lines))

		try:
			self.arch_chroot('locale-gen')
		except SysCallError as e:
			error(f'Failed to run locale-gen on target: {e}')
			return False

		# always fully qualified: bare SUPPORTED entries ("en_IL UTF-8") compile
		# under the bare name, but localedef also registers a normalized-codeset
		# alias (locarchive.c), so LANG=en_IL.UTF-8 resolves and UTF-8 stays
		# visible to tools sniffing LANG (tmux et al.)
		(self.target / 'etc/locale.conf').write_text(f'LANG={lang}.{encoding}{modifier}\n')
		info(f'Set locale LANG={lang}.{encoding}{modifier}')
		return True

	def set_timezone(self, zone: str) -> bool:
		if not zone:
			debug('No timezone configured, leaving target default')
			return True

		# Validate against the target's tzdata, not the host's: the symlink
		# resolves inside the chroot, and a host may lack FHS zoneinfo (NixOS).
		if (self.target / 'usr/share/zoneinfo' / zone).exists():
			(self.target / 'etc' / 'localtime').unlink(missing_ok=True)
			self.arch_chroot(['ln', '-s', f'/usr/share/zoneinfo/{zone}', '/etc/localtime'])
			info(f'Set timezone to {zone}')
			return True

		warn(f'Time zone {zone} does not exist, continuing with system default')

		return False

	def activate_time_synchronization(self) -> None:
		info('Activating systemd-timesyncd for time synchronization using Arch Linux and ntp.org NTP servers')
		self.enable_service('systemd-timesyncd')

	def enable_espeakup(self) -> None:
		info('Enabling espeakup.service for speech synthesis (accessibility)')
		self.enable_service('espeakup')

	def enable_periodic_trim(self) -> None:
		info('Enabling periodic TRIM')
		# fstrim is owned by util-linux, a dependency of both base and systemd.
		self.enable_service('fstrim.timer')

	def _systemctl_target(self, action: str, service: str) -> None:
		# host systemctl drives the target offline via --root=. A non-systemd
		# host (alpine, ...) has no systemctl binary, so run the target's own
		# systemctl inside the chroot instead. enable/disable only write unit
		# symlinks, so they work without a running pid1 in the chroot.
		if shutil.which('systemctl'):
			SysCommand(f'systemctl --root={self.target} {action} {service}')
		else:
			self.arch_chroot(f'systemctl {action} {service}')

	def enable_service(self, services: str | list[str]) -> None:
		if isinstance(services, str):
			services = [services]

		for service in services:
			info(f'Enabling service {service}')

			try:
				self._systemctl_target('enable', service)
			except SysCallError as err:
				raise ServiceError(f'Unable to start service {service}: {err}') from err

	def enable_linger(self, user: str) -> None:
		linger_dir = self.target / 'var/lib/systemd/linger'
		linger_dir.mkdir(parents=True, exist_ok=True)
		(linger_dir / user).touch()
		info(f'Enabled linger for user {user}')

	def enable_user_service(self, user: str, services: str | list[str]) -> None:
		if isinstance(services, str):
			services = [services]

		wants_dir = self.target / f'home/{user}/.config/systemd/user/default.target.wants'
		wants_dir.mkdir(parents=True, exist_ok=True)

		for service in services:
			info(f'Enabling user service {service} for {user}')
			unit_path = Path(f'/usr/lib/systemd/user/{service}')
			symlink = wants_dir / service
			if not symlink.exists():
				symlink.symlink_to(unit_path)

		self.chown_tree(user, f'/home/{user}/.config')

	def enable_services_from_config(self, services: list[str | UserService]) -> None:
		from archinstoo.lib.models.service import UserService

		system_services = [s for s in services if isinstance(s, str)]
		user_services = [s for s in services if isinstance(s, UserService)]

		if system_services:
			self.enable_service(system_services)

		for us in user_services:
			self.enable_user_service(us.user, us.unit)
			if us.linger:
				self.enable_linger(us.user)

	def disable_service(self, services_disable: str | list[str]) -> None:
		if isinstance(services_disable, str):
			services_disable = [services_disable]

		for service in services_disable:
			info(f'Disabling service {service}')

			try:
				self._systemctl_target('disable', service)
			except SysCallError as err:
				raise ServiceError(f'Unable to disable service {service}: {err}') from err

	@property
	def arch_chroot_prefix(self) -> list[str]:
		# `arch-chroot -S` runs the chroot through systemd-run, which a foreign
		# host (Debian, ...) has no running systemd to provide; drop -S there so
		# it falls back to plain chroot(8).
		prefix = ['arch-chroot']
		if not Os.running_from_foreign():
			prefix.append('-S')
		prefix.append(str(self.target))
		return prefix

	def run_command(self, cmd: str, peek_output: bool = False) -> SysCommand:
		if self.target == Path('/'):
			return SysCommand(cmd, peek_output=peek_output)
		return SysCommand(f'{" ".join(self.arch_chroot_prefix)} {cmd}', peek_output=peek_output)

	def arch_chroot(
		self,
		cmd: str | list[str],
		run_as: str | None = None,
		peek_output: bool = False,
		env: dict[str, str] | None = None,
	) -> SysCommand | CompletedProcess[bytes]:
		# argv list form avoids argv/shell-injection when arguments come from user or config input.
		if isinstance(cmd, list):
			if run_as:
				cmd = ['su', '-', run_as, '-c', shlex.join(cmd)]
			argv = cmd if self.target == Path('/') else [*self.arch_chroot_prefix, *cmd]
			return run(argv, env=env)  # env: secrets (NEWPIN) stay off argv and out of cmd_history

		if run_as:
			cmd = f'su - {run_as} -c {shlex.quote(cmd)}'

		return self.run_command(cmd, peek_output=peek_output)

	def drop_to_shell(self) -> None:
		# shell=True is intentional: gives the user a real interactive shell session.
		subprocess.check_call(f'arch-chroot {self.target}', shell=True)  # noqa: S602

	def configure_nic(self, nic: Nic) -> None:
		conf = nic.as_systemd_config()

		with (self.target / f'etc/systemd/network/10-{nic.iface}.network').open('a') as netconf:
			netconf.write(str(conf))
		info(f'Wrote network config for {nic.iface}')

	def use_resolved(self) -> None:
		# every network type; the stub symlink is what switches NetworkManager
		# to dns=systemd-resolved https://wiki.archlinux.org/title/Systemd-resolved#DNS
		self.enable_service('systemd-resolved')

		resolv = self.target / 'etc/resolv.conf'
		resolv.unlink(missing_ok=True)

		# the stub only resolves once systemd-resolved runs on the target. From a
		# foreign (non-systemd) host that flow isn't guaranteed, so copy the
		# host's working resolv.conf content instead of a dangling symlink.
		if Os.running_from_foreign():
			host_resolv = Path('/etc/resolv.conf')
			if host_resolv.is_file():  # follows symlink, False if dangling
				resolv.write_text(host_resolv.read_text())
				debug(f'Copied host {host_resolv} to target (foreign host)')
			else:
				debug('No host /etc/resolv.conf to copy, leaving target unset')
			return

		resolv.symlink_to('/run/systemd/resolve/stub-resolv.conf')
		debug(f'Linked {resolv} to systemd-resolved stub')

	def copy_iso_network_config(self, enable_services: bool = False) -> bool:
		# Live mode targets the running system: configs already in place,
		# copying a path onto itself raises OSError (Errno 22). Skip the
		# copies, keep service enablement.
		on_host = self.target == Path('/')

		# Copy (if any) iwd password and config files
		iwd_dir = LPath('/var/lib/iwd')
		if psk_files := list(iwd_dir.glob('*.psk')):
			info(f'Copying {len(psk_files)} iwd profile(s) to target')
			if not on_host:
				iwd_target = self.target / iwd_dir.relative_to_root()
				iwd_target.mkdir(parents=True, exist_ok=True)

				for psk in psk_files:
					psk.copy(iwd_target / psk.name, preserve_metadata=True)

			if enable_services:
				# If we haven't installed the base yet (function called pre-maturely)
				if self._helper_flags.get('base', False) is False:
					self._base_packages.extend(ISO_PSK_EXTRA)

					# This function will be called after minimal_installation()
					# as a hook for post-installs. This hook is only needed if
					# base is not installed yet.
					def post_install_enable_iwd_service() -> None:
						self.enable_service('iwd')

					self.post_base_install.append(post_install_enable_iwd_service)
				# Otherwise, we can go ahead and add the required package
				# and enable it's service:
				else:
					self.pacman.strap(ISO_PSK_EXTRA)
					self.enable_service('iwd')

		# Copy (if any) systemd-networkd config files
		network_dir = LPath('/etc/systemd/network')
		if netconfigurations := list(network_dir.glob('*')):
			info(f'Copying {len(netconfigurations)} systemd-networkd config(s) to target')
			if not on_host:
				network_target = self.target / network_dir.relative_to_root()
				network_target.mkdir(parents=True, exist_ok=True)

				for netconf_file in netconfigurations:
					netconf_file.copy(network_target / netconf_file.name, preserve_metadata=True)

			if enable_services:
				# If we haven't installed the base yet (function called pre-maturely)
				if self._helper_flags.get('base', False) is False:

					def post_install_enable_networkd() -> None:
						self.enable_service('systemd-networkd')

					self.post_base_install.append(post_install_enable_networkd)
				# Otherwise, we can go ahead and enable the service
				else:
					self.enable_service('systemd-networkd')

		if not psk_files and not netconfigurations:
			debug('No iwd profiles or systemd-networkd configs found on ISO')

		return True

	def mkinitcpio(self, flags: list[str]) -> bool:
		with (self.target / 'etc/mkinitcpio.conf').open('r+') as mkinit:
			content = mkinit.read()
			content = re.sub(r'\nMODULES=(.*)', f'\nMODULES=({" ".join(self._modules)})', content)
			content = re.sub(r'\nBINARIES=(.*)', f'\nBINARIES=({" ".join(self._binaries)})', content)
			content = re.sub(r'\nFILES=(.*)', f'\nFILES=({" ".join(self._files)})', content)
			content = re.sub(r'\nHOOKS=(.*)', f'\nHOOKS=({" ".join(self._hooks)})', content)
			mkinit.seek(0)
			mkinit.truncate()
			mkinit.write(content)

		debug(f'mkinitcpio.conf HOOKS=({" ".join(self._hooks)}) MODULES=({" ".join(self._modules)}) FILES=({" ".join(self._files)})')
		info('Building initramfs...', step=True)

		try:
			self.arch_chroot(f'mkinitcpio {" ".join(flags)}', peek_output=True)
			return True
		except SysCallError as e:
			warn(f'mkinitcpio failed: {e}')
			if e.worker_log:
				log(e.worker_log.decode())
			return False

	def _get_microcode(self) -> Path | None:
		if not SysInfo.is_vm() and (vendor := SysInfo.cpu_vendor()):
			return vendor.get_ucode()
		return None

	def _prepare_fs_type(
		self,
		fs_type: FilesystemType,
		mountpoint: Path | None,
	) -> None:
		if (pkg := fs_type.installation_pkg) is not None:
			self._base_packages.append(pkg)

		# Install linux-headers and bcachefs-dkms if bcachefs is selected
		# xxhash is required by objtool (part of linux-headers) at dkms build time
		if fs_type == FilesystemType.BCACHEFS:
			self._base_packages.extend(f'{kernel}-headers' for kernel in self.kernels)
			self._base_packages.extend(__bcachefs_packages__)

		# https://github.com/archlinux/archinstall/issues/1837
		# https://github.com/koverstreet/bcachefs/issues/916
		if fs_type.fs_type_mount in ('btrfs', 'bcachefs'):
			self._disable_fstrim = True

		if fs_type == FilesystemType.BCACHEFS:
			if 'bcachefs' not in self._modules:
				debug('Adding bcachefs module to initramfs')
				self._modules.append('bcachefs')
			if 'bcachefs' not in self._hooks and 'block' in self._hooks:
				debug('Inserting bcachefs hook after block')
				self._hooks.insert(self._hooks.index('block') + 1, 'bcachefs')

		# There is not yet an fsck tool for NTFS. If it's being used for the root filesystem, the hook should be removed.
		if fs_type.fs_type_mount == 'ntfs3' and mountpoint == self.target and 'fsck' in self._hooks:
			debug('Removing fsck hook: no fsck tool for ntfs3 root')
			self._hooks.remove('fsck')

	def _prepare_encrypt(self, before: str = 'filesystems') -> None:
		if 'sd-encrypt' not in self._hooks:
			debug(f'Inserting sd-encrypt hook before {before}')
			self._hooks.insert(self._hooks.index(before), 'sd-encrypt')

	def minimal_installation(
		self,
		optional_repositories: list[Repository] | None = None,
		mkinitcpio: bool = True,
		hostname: str | None = None,
		locale_config: LocaleConfiguration | None = None,
		timezone: str | None = None,
	) -> None:
		if optional_repositories is None:
			optional_repositories = []

		info(f'Installing base system: kernels={", ".join(self.kernels)}, hostname={hostname or "(unset)"}', step=True)

		if self._disk_config.lvm_config:
			self.add_additional_packages(__lvm_packages__)
			debug(f'Inserting {LVM} hook before filesystems')
			self._hooks.insert(self._hooks.index('filesystems') - 1, LVM)

			for vg in self._disk_config.lvm_config.vol_groups:
				for vol in vg.volumes:
					if vol.fs_type is not None:
						self._prepare_fs_type(vol.fs_type, vol.mountpoint)

			types = (EncryptionType.LVM_ON_LUKS, EncryptionType.LUKS_ON_LVM)
			if self._disk_encryption.encryption_type in types:
				self._prepare_encrypt(LVM)
		else:
			for mod in self._disk_config.device_modifications:
				for part in mod.partitions:
					if part.fs_type is None:
						continue

					self._prepare_fs_type(part.fs_type, part.mountpoint)

					if part in self._disk_encryption.partitions:
						self._prepare_encrypt()

		if self._disk_encryption.fido2_device:
			self._base_packages.extend(__fido2_packages__)

		if ucode := self._get_microcode():
			(self.target / 'boot' / ucode).unlink(missing_ok=True)
			debug(f'Adding microcode package {ucode.stem}')
			self._base_packages.append(ucode.stem)
		else:
			debug('Archinstoo will not install any ucode.')

		debug(f'Optional repositories: {optional_repositories}')

		# pacstrap resolves packages through the live conf, so the repos have
		# to be enabled there before it runs
		live_conf = PacmanConfig(None)
		live_conf.enable(optional_repositories)
		live_conf.apply()

		if locale_config:
			self.set_vconsole(locale_config)
			if locale_config.console_font.startswith('ter-'):
				self._base_packages.extend(__ter_font_packages__)

		self.pacman.strap(list(dict.fromkeys(self._base_packages)))
		self._helper_flags['base-strapped'] = True

		# same repos again, on the stock conf pacstrap just installed
		target_conf = PacmanConfig(self.target)
		target_conf.enable(optional_repositories)
		target_conf.apply()

		# Periodic TRIM may improve the performance and longevity of SSDs whilst
		# having no adverse effect on other devices. Most distributions enable
		# periodic TRIM by default.
		#
		# https://github.com/archlinux/archinstall/issues/880
		# https://github.com/archlinux/archinstall/issues/1837
		# https://github.com/archlinux/archinstall/issues/1841
		if not self._disable_fstrim:
			self.enable_periodic_trim()

		if hostname:
			self.set_hostname(hostname)

		if locale_config and not self.set_locale(locale_config):
			warn(f'Failed to set locale: {locale_config.sys_lang} {locale_config.sys_enc}')

		if timezone and not self.set_timezone(timezone):
			warn(f'Failed to set timezone: {timezone}')

		root_dir = self.target / 'root'
		if root_dir.exists():
			root_dir.chmod(0o700)
		else:
			debug(f'Root directory not found at {root_dir}, skipping chmod')

		if mkinitcpio and not self.mkinitcpio(['-P']):
			error('Error generating initramfs (continuing anyway)')

		self._helper_flags['base'] = True

		# Run registered post-install hooks
		for function in self.post_base_install:
			info(f'Running post-installation hook: {function}')
			function()

	def _btrfs_snapshot_type(self) -> SnapshotType | None:
		if not self._disk_config.has_default_btrfs_vols():
			return None
		btrfs_options = self._disk_config.btrfs_options
		snapshot_config = btrfs_options.snapshot_config if btrfs_options else None
		return snapshot_config.snapshot_type if snapshot_config else None

	def setup_btrfs_snapshot(
		self,
		snapshot_type: SnapshotType,
		bootloader: Bootloader | None = None,
	) -> None:
		if snapshot_type == SnapshotType.Snapper:
			debug('Setting up Btrfs snapper')
			self.pacman.strap(snapshot_type.packages)

			snapper: dict[str, str] = {
				'root': '/',
				'home': '/home',
			}

			for config_name, mountpoint in snapper.items():
				# snapper create-config makes its own .snapshots subvolume and errors if one exists
				# (e.g. a manual layout that pre-created it); skip rather than abort the whole install
				if (self.target / mountpoint.lstrip('/') / '.snapshots').exists():
					info(f'snapper: .snapshots already present at {mountpoint}, skipping create-config')
					continue

				command = [
					*self.arch_chroot_prefix,
					'snapper',
					'--no-dbus',
					'-c',
					config_name,
					'create-config',
					mountpoint,
				]

				try:
					SysCommand(command, peek_output=True)
				except SysCallError as err:
					raise DiskError(f'Could not setup Btrfs snapper: {err}') from err

			self.enable_service('snapper-timeline.timer')
			self.enable_service('snapper-cleanup.timer')

		elif snapshot_type == SnapshotType.Timeshift:
			debug('Setting up Btrfs timeshift')

			self.pacman.strap(snapshot_type.packages)
			self.enable_service('cronie')

		if bootloader and bootloader == Bootloader.Grub:
			debug('Setting up grub integration for either')
			self.pacman.strap(__grub_snapshot_packages__)
			configure_grub_btrfsd(self.target, snapshot_type)
			self.enable_service('grub-btrfsd')

	def setup_swap(self, config: SwapConfiguration) -> None:
		if config.zram:
			self._setup_zram(config.algorithm, config.recomp_algorithm)
		if config.hibernation:
			try:
				self._setup_swapfile(config.size_gib)
			except (SysCallError, DiskError) as err:
				# hibernation is an enhancement, not worth aborting a
				# finished-installing system over (cf. allow_ssh)
				warn(f'Failed to set up hibernation swap file: {err}')

	def _setup_zram(self, algo: ZramAlgorithm, recomp_algo: ZramAlgorithm | None) -> None:
		info('Setting up swap on zram')
		self.pacman.strap(__zram_packages__)

		with (self.target / 'etc/systemd/zram-generator.conf').open('w') as zram_conf:
			zram_conf.write('[zram0]\n')
			zram_conf.write('zram-size = ram / 2\n')
			if algo != ZramAlgorithm.Default:
				comp_line = algo.value
				if recomp_algo:
					comp_line += f' {recomp_algo.value} (type=idle)'
				zram_conf.write(f'compression-algorithm = {comp_line}\n')

		self.enable_service('systemd-zram-setup@zram0')

		self._zram_enabled = True

	# No resume hook (the systemd initramfs hook ships it) and no kernel
	# params on UEFI (systemd-sleep records the HibernateLocation EFI var);
	# only BIOS needs resume=/resume_offset=.
	def _setup_swapfile(self, size_gib: int) -> None:
		# ceil MemTotal (kB) to GiB: the image must fit even on a full RAM
		size = size_gib or -(-SysInfo.mem_total() // 2**20)
		fs_type = SysCommand(['findmnt', '-no', 'FSTYPE', str(self.target)]).decode().strip()
		if fs_type == 'bcachefs':
			# mkswap --file succeeds but swapon returns EINVAL: the kernel
			# side has no swap file support. zram still covers swap
			raise DiskError('bcachefs cannot host a swap file, hibernation skipped')
		info(f'Setting up {size}GiB swap file on {fs_type}')

		if fs_type == 'btrfs':
			# nested subvolume: snapshots of the parent don't recurse into
			# it, so root snapshots keep working with the swapfile in place
			swapfile = '/swap/swapfile'
			self.arch_chroot(['btrfs', 'subvolume', 'create', '/swap'])
			self.arch_chroot(['btrfs', 'filesystem', 'mkswapfile', '--size', f'{size}g', '--uuid', 'clear', swapfile])
		else:
			swapfile = '/swapfile'
			self.arch_chroot(['mkswap', '-U', 'clear', '--size', f'{size}G', '--file', swapfile])

		self._fstab_entries.append(f'{swapfile}\tnone\tswap\tdefaults\t0\t0')

		if not SysInfo.has_uefi():
			fs_uuid = SysCommand(['findmnt', '-no', 'UUID', str(self.target)]).decode().strip()
			if fs_type == 'btrfs':
				result = self.arch_chroot(['btrfs', 'inspect-internal', 'map-swapfile', '-r', swapfile])
				offset = result.stdout.decode().strip() if isinstance(result, CompletedProcess) else str(result).strip()
			else:
				# the kernel wants the offset in PAGE_SIZE units, filefrag's
				# default unit is the fs block size; page size is an arch
				# property (arm64 kernels ship 4k/16k/64k), not always 4096
				page_size = os.sysconf('SC_PAGE_SIZE')
				result = self.arch_chroot(['filefrag', f'-b{page_size}', '-v', swapfile])
				out = result.stdout.decode() if isinstance(result, CompletedProcess) else str(result)
				match = re.search(r'^\s*0:\s+\d+\.\.\s*\d+:\s+(\d+)', out, re.MULTILINE)
				if not match:
					raise DiskError(f'Could not determine swap file offset from filefrag:\n{out}')
				offset = match.group(1)
			self._kernel_params.extend([f'resume=UUID={fs_uuid}', f'resume_offset={offset}'])

	def setup_sysctl(self, entries: list[str]) -> None:
		if not entries:
			return

		info('Writing sysctl configuration')
		sysctl_dir = self.target / 'etc/sysctl.d'
		sysctl_dir.mkdir(parents=True, exist_ok=True)

		conf = sysctl_dir / '99-archinstoo.conf'
		conf.write_text('\n'.join(entries) + '\n')

	def add_bootloader(
		self,
		bootloader: Bootloader,
		uki_enabled: bool = False,
		removable: bool = False,
		quiet: bool = False,
		splash: bool = False,
		serial_console: str | None = None,
	) -> None:
		# Run before bootloader install so kernel cmdline reflects rd.luks.options
		# (tpm2-device/fido2-device) but is extensively gated and a no-op if not present/selected
		enroll_tpm2(self.target, self._disk_encryption, self.arch_chroot)
		enroll_fido2(self.target, self._disk_encryption)

		if quiet and 'quiet' not in self._kernel_params:
			self.add_kernel_param('quiet')

		if serial_console and (param := f'console={serial_console}') not in self._kernel_params:
			self.add_kernel_param(param)

		efi_partition = self._disk_config.get_efi_partition()
		boot_partition = self._disk_config.get_boot_partition()
		root = self._disk_config.get_root()

		if boot_partition is None:
			if SysInfo.has_uefi() and efi_partition is not None:
				boot_partition = efi_partition
			else:
				raise ValueError(f'Could not detect boot at mountpoint {self.target}')

		if root is None:
			raise ValueError(f'Could not detect root at mountpoint {self.target}')

		info(f'Adding bootloader {bootloader.display_name()} to {boot_partition.dev_path}', step=True)

		if not SysInfo.has_uefi() and not bootloader.has_bios_support():
			raise HardwareIncompatibilityError

		# validate removable bootloader option
		if removable:
			if not SysInfo.has_uefi():
				warn('Removable install requested but system is not UEFI; disabling.')
				removable = False
			elif not bootloader.has_removable_support():
				warn(f'Bootloader {bootloader.display_name()} lacks removable support; disabling.')
				removable = False

		# grub-btrfs cannot consume a UKI for snapshot entries; keep standalone initramfs alongside.
		keep_standalone = uki_enabled and bootloader == Bootloader.Grub and self._btrfs_snapshot_type() is not None

		BootloaderInstaller(self, self._disk_encryption, self._kernel_params, self._zram_enabled).install(
			bootloader,
			boot_partition,
			efi_partition,
			root,
			uki_enabled=uki_enabled,
			removable=removable,
			splash=splash,
			keep_standalone_initramfs=keep_standalone,
		)
		self._helper_flags['bootloader'] = bootloader.value

	def add_additional_packages(self, packages: str | list[str]) -> None:
		return self.pacman.strap(packages)

	def add_kernel_param(self, params: str | list[str]) -> None:
		if isinstance(params, str):
			params = [params]
		debug(f'Adding kernel param(s): {params}')
		self._kernel_params.extend(params)

	def enable_sudo(self, user: User, group: bool = False) -> None:
		info(f'Enabling sudo permissions for {user.username}')

		sudoers_dir = self.target / 'etc/sudoers.d'

		# Creates directory if not exists
		if not sudoers_dir.exists():
			sudoers_dir.mkdir(parents=True)
			# Guarantees sudoer confs directory recommended perms
			sudoers_dir.chmod(0o440)
			# Appends a reference to the sudoers file, because if we are here sudoers.d did not exist yet
			with (self.target / 'etc/sudoers').open('a') as sudoers:
				sudoers.write('@includedir /etc/sudoers.d\n')

		# We count how many files are there already so we know which number to prefix the file with
		num_of_rules_already = len(list(sudoers_dir.iterdir()))
		file_num_str = f'{num_of_rules_already:02d}'  # We want 00_user1, 01_user2, etc

		# Guarantees that username str does not contain invalid characters for a linux file name:
		# \ / : * ? " < > |
		safe_username_file_name = re.sub(r'(\\|\/|:|\*|\?|"|<|>|\|)', '', user.username)

		rule_file = sudoers_dir / f'{file_num_str}_{safe_username_file_name}'

		with rule_file.open('a') as sudoers:
			sudoers.write(f'{"%" if group else ""}{user.username} ALL=(ALL) ALL\n')

		# Guarantees sudoer conf file recommended perms
		rule_file.chmod(0o440)

	# under seatd, compositors need seat membership to reach /run/seatd.sock (DRM/input).
	# group exists only when the seatd package landed (sysusers); skip otherwise so
	# usermod can't abort the install on logind/polkit systems.
	def add_to_seat_group(self, usernames: list[str]) -> None:
		group_lines = self.target.joinpath('etc/group').read_text().splitlines()
		if not any(line.startswith('seat:') for line in group_lines):
			debug('No seat group on target (seatd not installed), skipping seat membership')
			return
		for name in usernames:
			debug(f'Adding {name} to seat group')
			self.arch_chroot(['usermod', '-a', '-G', 'seat', name])

	def enable_doas(self, user: User) -> None:
		info(f'Enabling doas permissions for {user.username}')

		doas_conf = self.target / 'etc/doas.conf'

		with doas_conf.open('a') as doas:
			doas.write(f'permit {user.username} as root\n')

		# doas.conf must be owned by root and not writable by others
		doas_conf.chmod(0o644)

	def create_users(
		self,
		users: User | list[User],
		privilege_escalation: PrivilegeEscalation | None = PrivilegeEscalation.Sudo,
	) -> None:
		if not isinstance(users, list):
			users = [users]

		info(f'Creating {len(users)} user account(s): {", ".join(u.username for u in users)}', step=True)

		# Install the privilege escalation package
		if privilege_escalation is not None and User.any_elevated(users):
			self.pacman.strap(privilege_escalation.packages())

		self._configure_makepkg(privilege_escalation)

		for user in users:
			self._create_user(user, privilege_escalation)

	def _configure_makepkg(self, privilege_escalation: PrivilegeEscalation | None) -> None:
		# makepkg tries sudo then su by default, only doas/run0 need an override
		if privilege_escalation is None:
			return

		auth_binary = {
			PrivilegeEscalation.Doas: 'doas',
			PrivilegeEscalation.Run0: 'run0',
		}.get(privilege_escalation)

		if auth_binary is None:
			debug(f'{privilege_escalation.value} uses makepkg default PACMAN_AUTH, nothing to set')
			return

		makepkg_conf = self.target / 'etc/makepkg.conf'
		if not makepkg_conf.exists():
			warn(f'{makepkg_conf} missing, PACMAN_AUTH not set for {auth_binary}')
			return

		content = makepkg_conf.read_text()
		content = content.replace('#PACMAN_AUTH=()', f'PACMAN_AUTH=({auth_binary})')
		makepkg_conf.write_text(content)
		debug(f'Set PACMAN_AUTH=({auth_binary}) in makepkg.conf')

	def _create_user(
		self,
		user: User,
		privilege_escalation: PrivilegeEscalation | None = PrivilegeEscalation.Sudo,
	) -> None:
		info(f'Creating user {user.username}')

		cmd = ['useradd', '-m']

		if user.elev:
			cmd += ['-G', 'wheel']

		cmd.append(user.username)

		try:
			self.arch_chroot(cmd)
		except CalledProcessError:
			# user may already exist (e.g. installing onto running system)
			info(f'User {user.username} already exists, skipping creation')

		self.set_user_password(user)

		for group in user.groups:
			debug(f'Adding {user.username} to group {group}')
			self.arch_chroot(['gpasswd', '-a', user.username, group])

		if user.elev:
			match privilege_escalation:
				case PrivilegeEscalation.Sudo:
					self.enable_sudo(user)
				case PrivilegeEscalation.Doas:
					self.enable_doas(user)
				case PrivilegeEscalation.Run0 | None:
					pass  # run0/su via wheel group - no extra config needed

		for stash_url in user.stash_urls:
			self._clone_user_stash(user.username, stash_url)

	def _clone_user_stash(self, username: str, stash_url: str) -> None:
		info(f'Cloning {stash_url} for {username}')

		self.add_additional_packages(__stash_packages__)

		url, _, branch = stash_url.partition('#')
		repo_name = url.rstrip('/').split('/')[-1].removesuffix('.git')
		stash_dir = f'/home/{username}/.stash'
		clone_cmd = ['git', 'clone', '--depth', '1']
		if branch:
			clone_cmd += ['-b', branch]
		clone_cmd += [url, f'{stash_dir}/{repo_name}']

		try:
			self.arch_chroot(['mkdir', '-p', stash_dir])
			self.arch_chroot(clone_cmd)
			self.chown_tree(username, stash_dir)
		except CalledProcessError as err:
			error(f'Failed to clone stash for {username}: {err}')

	def set_user_password(self, user: User) -> bool:
		info(f'Setting password for {user.username}')

		if not user.password:
			debug('User password not set')
			return False

		enc_password = user.password.enc_password

		if not enc_password:
			debug('User password is empty')
			return False

		input_data = f'{user.username}:{enc_password}'.encode()
		cmd = [*self.arch_chroot_prefix, 'chpasswd', '--encrypted']

		try:
			run(cmd, input_data=input_data)
			return True
		except CalledProcessError as err:
			debug(f'Error setting user password: {err}')
			return False

	def lock_root_account(self) -> bool:
		info('Locking root account')

		try:
			self.arch_chroot('passwd -l root')
			return True
		except SysCallError as err:
			error(f'Failed to lock root account: {err}')
			return False

	def chown_tree(self, username: str, path: str) -> None:
		# installer writes into $HOME as root; hand the tree back before first login
		debug(f'chown -R {username}:{username} {path}')
		self.arch_chroot(['chown', '-R', f'{username}:{username}', path])

	def set_vconsole(self, locale_config: LocaleConfiguration) -> None:
		kb_vconsole: str = locale_config.kb_layout
		font_vconsole: str = locale_config.console_font

		vconsole_dir: Path = self.target / 'etc'
		vconsole_dir.mkdir(parents=True, exist_ok=True)
		vconsole_path: Path = vconsole_dir / 'vconsole.conf'

		vconsole_content = f'KEYMAP={kb_vconsole}\n'
		vconsole_content += f'FONT={font_vconsole}\n'

		vconsole_path.write_text(vconsole_content)
		info(f'Wrote to {vconsole_path} using {kb_vconsole} and {font_vconsole}')

	def set_environment(self, env_vars: dict[str, str]) -> None:
		# pam_env exports /etc/environment into the session, graphical ones
		# included, which is the only path Wayland has for XKB_DEFAULT_* and
		# the one $TERMINAL rides on. Guarded per key so a second writer (or a
		# re-run) does not stack duplicate lines.
		env_path = self.target / 'etc/environment'
		existing = env_path.read_text() if env_path.exists() else ''
		defined = {line.split('=', 1)[0] for line in existing.splitlines()}

		fresh = {k: v for k, v in env_vars.items() if k not in defined}
		if not fresh:
			debug(f'Env vars already defined, not overwriting: {sorted(env_vars)}')
			return

		env_path.write_text(existing + ''.join(f'{k}={v}\n' for k, v in fresh.items()))
		info(f'Wrote {", ".join(fresh)} to {env_path}')

	def set_keyboard(self, locale_config: LocaleConfiguration) -> bool:
		# Graphical (X11/Wayland) keyboard config, separate from the console
		# keymap in vconsole.conf. Writes the Xorg InputClass (00-keyboard.conf)
		# and the libxkbcommon env Wayland compositors read (XKB_DEFAULT_*).
		# No-op unless a layout is set, leaving graphical sessions at the
		# libxkbcommon 'us' default. Selections come pre-validated from the menu.
		layout = locale_config.xkb_layout
		if not layout.strip():
			debug('No graphical (XKB) keyboard layout set, skipping')
			return False

		model = locale_config.xkb_model
		variant = locale_config.xkb_variant
		options = locale_config.xkb_options

		# Xorg: only emit the Options that are set (layout always, rest optional)
		xorg_opts = [('XkbLayout', layout)]
		if model:
			xorg_opts.append(('XkbModel', model))
		if variant:
			xorg_opts.append(('XkbVariant', variant))
		if options:
			xorg_opts.append(('XkbOptions', options))

		opt_lines = '\n'.join(f'    Option "{k}" "{v}"' for k, v in xorg_opts)
		content = f'Section "InputClass"\n    Identifier "system-keyboard"\n    MatchIsKeyboard "on"\n{opt_lines}\nEndSection\n'

		xorg_conf_dir = self.target / 'etc/X11/xorg.conf.d'
		xorg_conf_dir.mkdir(parents=True, exist_ok=True)
		(xorg_conf_dir / '00-keyboard.conf').write_text(content)
		info(f'Wrote X11 keyboard config: layout={layout} variant={variant or "-"}')

		# Wayland: libxkbcommon ignores vconsole.conf and 00-keyboard.conf,
		# so the layout has to reach the session as env vars.
		env_vars = {'XKB_DEFAULT_LAYOUT': layout}
		if model:
			env_vars['XKB_DEFAULT_MODEL'] = model
		if variant:
			env_vars['XKB_DEFAULT_VARIANT'] = variant
		if options:
			env_vars['XKB_DEFAULT_OPTIONS'] = options

		self.set_environment(env_vars)

		return True


def run_custom_user_commands(commands: list[str], installation: Installer) -> None:
	for index, command in enumerate(commands):
		script_path = LPath(f'/var/tmp/user-command.{index}.sh')  # noqa: S108 - path inside install target, not host /tmp
		chroot_path = installation.target / script_path.relative_to_root()

		# Do not throw error instead warn
		info(f'Executing custom command "{command}" ...')
		chroot_path.write_text(command)

		try:
			installation.arch_chroot(f'bash {script_path}')
		except SysCallError as e:
			warn(f'Custom command "{command}" failed: {e}')
		finally:
			chroot_path.unlink()
