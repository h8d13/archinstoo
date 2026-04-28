import os
import re
import shlex
import shutil
import stat
import subprocess
import textwrap
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CalledProcessError
from types import TracebackType
from typing import Any, Self

from archinstoo.lib.disk.device_handler import DeviceHandler
from archinstoo.lib.disk.lvm import lvm_import_vg, lvm_pvseg_info, lvm_vol_change
from archinstoo.lib.disk.utils import get_lsblk_info, get_parent_device_path, mount, swapon
from archinstoo.lib.linux_path import LPath
from archinstoo.lib.models.application import ZramAlgorithm
from archinstoo.lib.models.device import (
	DiskEncryption,
	DiskLayoutConfiguration,
	EncryptionType,
	FilesystemType,
	LuksPbkdf,
	LvmVolume,
	PartitionModification,
	SnapshotType,
	SubvolumeModification,
)
from archinstoo.lib.models.firmware import FirmwareConfiguration
from archinstoo.lib.models.packages import Repository
from archinstoo.lib.pathnames import MIRRORLIST, PACMAN_CONF
from archinstoo.lib.pm import installed_package
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import Tui

from .args import ArchConfigHandler
from .disk.luks import Luks2, unlock_luks2_dev
from .exceptions import DiskError, HardwareIncompatibilityError, RequirementError, ServiceException, SysCallError
from .general import SysCommand, run
from .hardware import SysInfo
from .models.authentication import PrivilegeEscalation
from .models.bootloader import Bootloader
from .models.locale import LocaleConfiguration
from .models.mirrors import PacmanConfiguration
from .models.network import Nic
from .models.users import User
from .output import debug, error, info, log, logger, warn
from .pm import Pacman
from .pm.config import PacmanConfig

# Base packages installed by default (firmware added based on FirmwareConfiguration)
# mkinitcpio is listed explicitly so pacstrap installs it deterministically. Otherwise
# pacman picks the first initramfs provider from the host's pacman.conf, which on non-Arch
# hosts (EndeavourOS prefers dracut, etc.) breaks the installer's mkinitcpio() and
# _config_uki() methods that assume mkinitcpio is present in the chroot.
__base_packages__ = ['base', 'mkinitcpio']

# Available kernel options
__kernels__ = ['linux', 'linux-lts', 'linux-zen', 'linux-hardened']

# Additional packages that are installed if the user is running the Live ISO with accessibility tools enabled
__accessibility_packages__ = ['brltty', 'espeakup', 'alsa-utils']


class Installer:
	def __init__(
		self,
		target: Path,
		disk_config: DiskLayoutConfiguration,
		base_packages: list[str] = [],
		kernels: list[str] | None = None,
		firmware: FirmwareConfiguration | None = None,
		*,
		handler: ArchConfigHandler | None = None,
		device_handler: DeviceHandler | None = None,
	):
		"""
		`Installer()` is the wrapper for most basic installation steps.
		It also wraps :py:func:`~archinstoo.Installer.pacstrap` among other things.
		"""
		from .args import Arguments

		self._handler = handler
		self._device_handler = device_handler or DeviceHandler()
		self._args = handler.args if handler else Arguments()
		self._bug_report_url = handler.config.bug_report_url if handler else 'https://github.com/h8d13/archinstoo/issues'

		self._base_packages = base_packages or __base_packages__.copy()
		self._base_packages.extend((firmware or FirmwareConfiguration()).packages())
		self.kernels = kernels or ['linux']
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

		self.post_base_install: list[Callable] = []  # type: ignore[type-arg]

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

		self.pacman = Pacman(self.target)

	@property
	def handler(self) -> ArchConfigHandler | None:
		return self._handler

	def set_helper_flag(self, key: str, value: str | bool | None) -> None:
		self._helper_flags[key] = value

	def __enter__(self) -> Self:
		return self

	def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool | None:
		if exc_type is not None:
			error(str(exc_value))

			self._sync_artifacts_to_target()
			Tui.print(str(tr('[!] A log file has been created here: {}').format(logger.path)))
			Tui.print(tr('Please submit this issue (and file) to {}/issues').format(self._bug_report_url))

			# Return None to propagate the exception
			return None

		info(tr('Syncing the system...'))
		os.sync()

		self._sync_artifacts_to_target()

		if not (missing_steps := self.post_install_check()):
			self._teardown_target()
			msg = f'Installation completed without any errors.\nLog files temporarily available at {logger.directory}.\nYou may reboot when ready.\n'
			log(msg, fg='green')

			return True
		warn('Some required steps were not successfully installed/configured before leaving the installer:')

		for step in missing_steps:
			warn(f' - {step}')

		warn(f'Detailed error logs can be found at: {logger.directory}')
		warn(f'Submit this zip file as an issue to {self._bug_report_url}/issues')

		return False

	def _sync_artifacts_to_target(self) -> None:
		# Copy the run log and saved user config into the target so they survive reboot
		# at /etc/archinstoo.d/<timestamp>-{install.log,config.json} for post-install debugging.
		try:
			dest_dir = self.target / 'etc' / 'archinstoo.d'
			dest_dir.mkdir(mode=0o755, exist_ok=True)

			ts = datetime.now(tz=UTC).strftime('%Y-%m-%dT%H-%M')
			log_src = logger.path
			cfg_src = logger.directory / 'user_configuration.json'

			if log_src.exists():
				log_dst = dest_dir / f'{ts}-install.log'
				shutil.copy2(log_src, log_dst)
				log_dst.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

			if cfg_src.exists():
				cfg_dst = dest_dir / f'{ts}-config.json'
				shutil.copy2(cfg_src, cfg_dst)
				cfg_dst.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
		except Exception as e:
			warn(f'Failed to sync install artifacts to target: {e}')

	def _teardown_target(self) -> None:
		# Order: unmount, deactivate VGs, close LUKS. Inner mappers close before the outer
		# ones that hold them.
		info('Tearing down target mounts and mappings')
		try:
			SysCommand(['umount', '-R', str(self.target)])
		except SysCallError:
			warn(f'{self.target} busy, retrying with lazy unmount')
			SysCommand(['umount', '-R', '-l', str(self.target)])

		enc = self._disk_encryption
		lvm_cfg = self._disk_config.lvm_config

		def _close_luks(dev_path: Path, mapper_name: str | None) -> None:
			if mapper_name is None:
				return
			Luks2(dev_path, mapper_name=mapper_name).lock()

		def _deactivate_vgs() -> None:
			if not lvm_cfg:
				return
			for vg in lvm_cfg.vol_groups:
				self._device_handler.lvm_vg_deactivate(vg.name)

		match enc.encryption_type:
			case EncryptionType.LUKS_ON_LVM:
				# LUKS sits on top of LVs, close LUKS first, then deactivate VGs.
				for vol in enc.lvm_volumes:
					_close_luks(vol.safe_dev_path, vol.mapper_name)
				_deactivate_vgs()
			case EncryptionType.LVM_ON_LUKS:
				# VGs sit on LUKS PV, deactivate VGs first, then close LUKS.
				_deactivate_vgs()
				for part in enc.partitions:
					_close_luks(part.safe_dev_path, part.mapper_name)
			case EncryptionType.LUKS:
				for part in enc.partitions:
					_close_luks(part.safe_dev_path, part.mapper_name)
			case EncryptionType.NO_ENCRYPTION:
				_deactivate_vgs()

	def _verify_service_stop(self) -> None:
		# Check for essential services statuses based on
		# architecture and parse results for prints
		# https://github.com/archlinux/archinstall/issues/3688
		# be more descriptive about status in code + what user sees
		if not self._args.skip_ntp:
			info(tr('Waiting for NTP time synchronization...'))

			started_wait = time.time()
			notified = False
			while True:
				if not notified and time.time() - started_wait > 5:
					notified = True
					warn(tr('NTP sync taking longer than expected, still waiting...'))

				time_val = SysCommand('timedatectl show --property=NTPSynchronized --value').decode()
				if time_val and time_val.strip() == 'yes':
					info(tr('NTP time synchronization completed'))
					break
				time.sleep(1)
		else:
			info(tr('Skipping NTP time sync (may cause issues if system time is incorrect)'))

		if not self._args.offline and SysInfo.arch() == 'x86_64':
			info('Waiting for reflector mirror selection...')
			reflector_state = self._service_state('reflector')
			timed_out = True
			for _ in range(60):
				if reflector_state in ('dead', 'failed', 'exited'):
					timed_out = False
					break
				time.sleep(1)
				reflector_state = self._service_state('reflector')

			if timed_out:
				warn('Reflector did not complete within 60 seconds, continuing anyway...')
			elif reflector_state == 'failed':
				warn('Reflector mirror selection failed')
			else:
				info('Reflector mirror selection completed')
		else:
			info('Skipping reflector (offline mode or non-x86_64 architecture)')

		if not self._args.skip_wkd:
			info(tr('Waiting for Arch Linux keyring sync...'))
			# Wait for the timer to kick in
			while self._service_started('archlinux-keyring-wkd-sync.timer') is None:
				time.sleep(1)

			# Wait for the service to enter a finished state
			keyring_state = self._service_state('archlinux-keyring-wkd-sync.service')
			while keyring_state not in ('dead', 'failed', 'exited'):
				time.sleep(1)
				keyring_state = self._service_state('archlinux-keyring-wkd-sync.service')

			if keyring_state == 'failed':
				warn(tr('Arch Linux keyring sync failed'))
			else:
				info(tr('Arch Linux keyring sync completed'))

	def sanity_check(self) -> None:
		self._verify_service_stop()

	def mount_ordered_layout(self) -> None:
		info('Mounting ordered layout')

		luks_handlers: dict[Any, Luks2] = {}

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

	def _mount_partition_layout(self, luks_handlers: dict[Any, Luks2]) -> None:
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

	def _mount_lvm_layout(self, luks_handlers: dict[Any, Luks2] = {}) -> None:
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
	) -> dict[PartitionModification, Luks2]:
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
	) -> dict[LvmVolume, Luks2]:
		return {
			vol: unlock_luks2_dev(
				vol.dev_path,
				vol.mapper_name,
				self._disk_encryption.encryption_password,
			)
			for vol in lvm_volumes
			if vol.mapper_name and vol.dev_path
		}

	def _mount_partition(self, part_mod: PartitionModification) -> None:
		if not part_mod.dev_path:
			return

		# it would be none if it's btrfs as the subvolumes will have the mountpoints defined
		if part_mod.mountpoint:
			target = self.target / part_mod.relative_mountpoint
			mount_fs = part_mod.fs_type.fs_type_mount if part_mod.fs_type else None
			options = list(part_mod.mount_options)

			# restrict ESP permissions so bootctl doesn't warn about world-accessible seed files
			if part_mod.is_efi() and part_mod.fs_type == FilesystemType.FAT32:
				for opt in ('fmask=0077', 'dmask=0077'):
					if opt not in options:
						options.append(opt)

			mount(part_mod.dev_path, target, mount_fs=mount_fs, options=options)
		elif part_mod.fs_type == FilesystemType.BTRFS:
			# Only mount BTRFS subvolumes that have mountpoints specified
			subvols_with_mountpoints = [sv for sv in part_mod.btrfs_subvols if sv.mountpoint is not None]
			if subvols_with_mountpoints:
				self._mount_btrfs_subvol(
					part_mod.dev_path,
					part_mod.btrfs_subvols,
					part_mod.mount_options,
				)
		elif part_mod.is_swap():
			swapon(part_mod.dev_path)

	def _mount_lvm_vol(self, volume: LvmVolume) -> None:
		if volume.fs_type != FilesystemType.BTRFS and volume.mountpoint and volume.dev_path:
			target = self.target / volume.relative_mountpoint
			mount(volume.dev_path, target, mount_fs=volume.fs_type.fs_type_mount, options=volume.mount_options)

		if volume.fs_type == FilesystemType.BTRFS and volume.dev_path:
			# Only mount BTRFS subvolumes that have mountpoints specified
			subvols_with_mountpoints = [sv for sv in volume.btrfs_subvols if sv.mountpoint is not None]
			if subvols_with_mountpoints:
				self._mount_btrfs_subvol(volume.dev_path, volume.btrfs_subvols, volume.mount_options)

	def _mount_luks_partition(self, part_mod: PartitionModification, luks_handler: Luks2) -> None:
		if not luks_handler.mapper_dev:
			return

		if part_mod.fs_type == FilesystemType.BTRFS and part_mod.btrfs_subvols:
			# Only mount BTRFS subvolumes that have mountpoints specified
			subvols_with_mountpoints = [sv for sv in part_mod.btrfs_subvols if sv.mountpoint is not None]
			if subvols_with_mountpoints:
				self._mount_btrfs_subvol(luks_handler.mapper_dev, part_mod.btrfs_subvols, part_mod.mount_options)
		elif part_mod.is_swap():
			swapon(luks_handler.mapper_dev)
			self._fstab_entries.append(f'{luks_handler.mapper_dev}\tnone\tswap\tdefaults\t0\t0')
		elif part_mod.mountpoint:
			target = self.target / part_mod.relative_mountpoint
			mount_fs = part_mod.fs_type.fs_type_mount if part_mod.fs_type else None
			mount(luks_handler.mapper_dev, target, mount_fs=mount_fs, options=part_mod.mount_options)

	def _mount_luks_volume(self, volume: LvmVolume, luks_handler: Luks2) -> None:
		if volume.fs_type != FilesystemType.BTRFS and volume.mountpoint and luks_handler.mapper_dev:
			target = self.target / volume.relative_mountpoint
			mount(luks_handler.mapper_dev, target, mount_fs=volume.fs_type.fs_type_mount, options=volume.mount_options)

		if volume.fs_type == FilesystemType.BTRFS and luks_handler.mapper_dev:
			# Only mount BTRFS subvolumes that have mountpoints specified
			subvols_with_mountpoints = [sv for sv in volume.btrfs_subvols if sv.mountpoint is not None]
			if subvols_with_mountpoints:
				self._mount_btrfs_subvol(luks_handler.mapper_dev, volume.btrfs_subvols, volume.mount_options)

	def _mount_btrfs_subvol(
		self,
		dev_path: Path,
		subvolumes: list[SubvolumeModification],
		mount_options: list[str] = [],
	) -> None:
		# Filter out subvolumes without mountpoints to avoid errors when sorting
		subvols_with_mountpoints = [sv for sv in subvolumes if sv.mountpoint is not None]
		for subvol in sorted(subvols_with_mountpoints, key=lambda x: x.relative_mountpoint):
			mountpoint = self.target / subvol.relative_mountpoint
			options = mount_options + [f'subvol={subvol.name}']
			mount(dev_path, mountpoint, mount_fs='btrfs', options=options)

	def generate_key_files(self) -> None:
		info(f'Generating key files for {self._disk_encryption.encryption_type.value}...')
		match self._disk_encryption.encryption_type:
			case EncryptionType.LUKS:
				self._generate_key_files_partitions()
			case EncryptionType.LUKS_ON_LVM:
				self._generate_key_file_lvm_volumes()
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
				if root_is_encrypted:
					# GRUB has limited memory for argon2id decryption;
					# constrain the keyfile slot too so GRUB can handle it
					is_boot = part_mod.is_boot()
					uses_argon2 = self._disk_encryption.pbkdf == LuksPbkdf.Argon2id
					pbkdf_memory = 32 * 1024 if is_boot and uses_argon2 else None
					iter_time = 200 if is_boot else None
					luks_handler.create_keyfile(self.target, pbkdf_memory=pbkdf_memory, iter_time=iter_time)
				else:
					# Root is unencrypted — don't write a keyfile to plaintext disk;
					# use a crypttab entry so systemd prompts for a passphrase instead.
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
					luks_handler.create_keyfile(self.target)
				else:
					luks_handler.create_crypttab_entry(self.target)

			if self._disk_encryption.auto_unlock_root and vol.is_root():
				self._create_root_keyfile(luks_handler)

	def _create_root_keyfile(self, luks_handler: Luks2, mapper_name: str = 'root') -> None:
		"""Create a keyfile at the sd-encrypt standard path and add it as a LUKS
		key slot so the volume can be auto-unlocked from the initramfs.
		sd-encrypt auto-detects keys at /etc/cryptsetup-keys.d/<name>.key."""
		kf_path = f'/etc/cryptsetup-keys.d/{mapper_name}.key'
		keyfile = self.target / kf_path.lstrip('/')

		debug(f'Creating key-file: {keyfile}')
		keyfile.parent.mkdir(parents=True, exist_ok=True)
		keyfile.write_bytes(os.urandom(2048))
		keyfile.chmod(0o000)

		luks_handler.add_key(keyfile)

		if kf_path not in self._files:
			self._files.append(kf_path)

	def enroll_tpm2(self) -> None:
		# Add a TPM2 keyslot to every encrypted device using systemd-cryptenroll.
		# Requires systemd-cryptenroll in the chroot (provided by base/systemd) and a TPM 2.0
		# device on the host. Existing passphrase keyslot remains as fallback.
		if not self._disk_encryption.tpm2_unlock:
			return
		if self._disk_encryption.encryption_type == EncryptionType.NO_ENCRYPTION:
			return
		if not (password := self._disk_encryption.encryption_password):
			warn('TPM2 enrollment skipped: no encryption password available')
			return

		devices: list[Path] = []
		if self._disk_encryption.encryption_type in (EncryptionType.LUKS, EncryptionType.LVM_ON_LUKS):
			devices.extend(p.safe_dev_path for p in self._disk_encryption.partitions)
		elif self._disk_encryption.encryption_type == EncryptionType.LUKS_ON_LVM:
			devices.extend(v.safe_dev_path for v in self._disk_encryption.lvm_volumes)

		if not devices:
			return

		pcrs = self._disk_encryption.tpm2_pcrs or '0+7'

		# Stash the existing passphrase as a transient unlock keyfile under the standard
		# LUKS keyfile dir (same convention as _create_root_keyfile).
		key_in_chroot = '/etc/cryptsetup-keys.d/.tpm2-bootstrap.key'
		key_in_target = self.target / key_in_chroot.lstrip('/')
		key_in_target.parent.mkdir(parents=True, exist_ok=True)

		try:
			key_in_target.write_bytes(password.plaintext.encode())
			key_in_target.chmod(0o400)

			for dev in devices:
				info(f'Enrolling TPM2 keyslot for {dev} bound to PCR {pcrs}')
				try:
					self.arch_chroot(
						[
							'systemd-cryptenroll',
							f'--unlock-key-file={key_in_chroot}',
							'--tpm2-device=auto',
							f'--tpm2-pcrs={pcrs}',
							str(dev),
						]
					)
				except CalledProcessError as e:
					stderr = e.stderr.decode(errors='replace').strip() if e.stderr else ''
					stdout = e.stdout.decode(errors='replace').strip() if e.stdout else ''
					warn(f'TPM2 enrollment failed for {dev} (exit {e.returncode}): {stderr or stdout or e}')
				except SysCallError as e:
					warn(f'TPM2 enrollment failed for {dev}: {e}')
		finally:
			if key_in_target.exists():
				key_in_target.unlink()

	def post_install_check(self, *args: str, **kwargs: str) -> list[str]:
		return [step for step, flag in self._helper_flags.items() if flag is False]

	def set_mirrors(
		self,
		pacman_configuration: PacmanConfiguration,
		on_target: bool = False,
	) -> None:
		"""
		Set the mirror configuration for the installation.

		:param pacman_configuration: The pacman configuration to use.
		:type pacman_configuration: PacmanConfiguration

		:on_target: Whether to set the mirrors on the target system or the live system.
		:param on_target: bool
		"""
		debug('Setting mirrors on ' + ('target' if on_target else 'live system'))

		if on_target:
			mirrorlist_path = self.target / MIRRORLIST.relative_to_root()
			pacman_conf_path = self.target / PACMAN_CONF.relative_to_root()
		else:
			mirrorlist_path = MIRRORLIST
			pacman_conf_path = PACMAN_CONF

		existing_content = pacman_conf_path.read_text()
		if repos_config := pacman_configuration.repositories_config(existing_content):
			debug(f'Pacman config: {repos_config}')
			with open(pacman_conf_path, 'a') as fp:
				fp.write(repos_config)

		# Speed test only for the live system, target reuses the same order
		regions_config = pacman_configuration.regions_config(speed_sort=not on_target)
		if regions_config:
			debug(f'Mirrorlist:\n{regions_config}')
			mirrorlist_path.write_text(regions_config)

		if custom_servers := pacman_configuration.custom_servers_config():
			debug(f'Custom servers:\n{custom_servers}')

			content = mirrorlist_path.read_text()
			mirrorlist_path.write_text(f'{custom_servers}\n\n{content}')

		# Persist pacman options (Color, ILoveCandy, etc.) to target
		if on_target and pacman_configuration.pacman_options:
			debug(f'Pacman options: {pacman_configuration.pacman_options}')
			target_config = PacmanConfig(self.target)
			target_config.enable_options(pacman_configuration.pacman_options)
			target_config.persist()

	def genfstab(self, flags: str = '-pU') -> None:
		fstab_path = self.target / 'etc' / 'fstab'
		info(f'Updating {fstab_path}')

		try:
			gen_fstab = SysCommand(f'genfstab {flags} -f {self.target} {self.target}').output()
		except SysCallError as err:
			raise RequirementError(f'Could not generate fstab, strapping in packages most likely failed (disk out of space?)\n Error: {err}')

		with open(fstab_path, 'ab') as fp:
			fp.write(gen_fstab)

		if not fstab_path.is_file():
			raise RequirementError('Could not create fstab file')

		with open(fstab_path, 'a') as fp:
			fp.writelines(f'{entry}\n' for entry in self._fstab_entries)

	def set_hostname(self, hostname: str) -> None:
		(self.target / 'etc/hostname').write_text(hostname + '\n')

	def set_locale(self, locale_config: LocaleConfiguration) -> bool:
		modifier = ''
		lang = locale_config.sys_lang
		encoding = locale_config.sys_enc

		# This is a temporary patch to fix #1200
		if '.' in locale_config.sys_lang:
			lang, potential_encoding = locale_config.sys_lang.split('.', 1)

			# Override encoding if encoding is set to the default parameter
			# and the "found" encoding differs.
			if locale_config.sys_enc == 'UTF-8' and locale_config.sys_enc != potential_encoding:
				encoding = potential_encoding

		# Make sure we extract the modifier, that way we can put it in if needed.
		if '@' in locale_config.sys_lang:
			lang, modifier = locale_config.sys_lang.split('@', 1)
			modifier = f'@{modifier}'
		# - End patch

		locale_gen = self.target / 'etc/locale.gen'
		locale_gen_lines = locale_gen.read_text().splitlines(True)

		# A locale entry in /etc/locale.gen may or may not contain the encoding
		# in the first column of the entry; check for both cases.
		entry_re = re.compile(rf'#{lang}(\.{encoding})?{modifier} {encoding}')

		lang_value = None
		for index, line in enumerate(locale_gen_lines):
			if entry_re.match(line):
				uncommented_line = line.removeprefix('#')
				locale_gen_lines[index] = uncommented_line
				locale_gen.write_text(''.join(locale_gen_lines))
				lang_value = uncommented_line.split()[0]
				break

		if lang_value is None:
			error(f"Invalid locale: language '{locale_config.sys_lang}', encoding '{locale_config.sys_enc}'")
			return False

		try:
			self.arch_chroot('locale-gen')
		except SysCallError as e:
			error(f'Failed to run locale-gen on target: {e}')
			return False

		(self.target / 'etc/locale.conf').write_text(f'LANG={lang_value}\n')
		return True

	def set_timezone(self, zone: str) -> bool:
		if not zone:
			return True
		if not len(zone):
			return True  # Redundant

		if (Path('/usr') / 'share' / 'zoneinfo' / zone).exists():
			(Path(self.target) / 'etc' / 'localtime').unlink(missing_ok=True)
			self.arch_chroot(['ln', '-s', f'/usr/share/zoneinfo/{zone}', '/etc/localtime'])
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

	def enable_service(self, services: str | list[str]) -> None:
		if isinstance(services, str):
			services = [services]

		for service in services:
			info(f'Enabling service {service}')

			try:
				SysCommand(f'systemctl --root={self.target} enable {service}')
			except SysCallError as err:
				raise ServiceException(f'Unable to start service {service}: {err}')

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

		# Fix ownership of .config tree
		self.chown(f'{user}:{user}', f'/home/{user}/.config', ['-R'])

	def enable_services_from_config(self, services: list[Any]) -> None:
		from .models.service import UserService

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
				SysCommand(f'systemctl --root={self.target} disable {service}')
			except SysCallError as err:
				raise ServiceException(f'Unable to disable service {service}: {err}')

	def run_command(self, cmd: str, peek_output: bool = False) -> SysCommand:
		if self.target == Path('/'):
			return SysCommand(cmd, peek_output=peek_output)
		return SysCommand(f'arch-chroot -S {self.target} {cmd}', peek_output=peek_output)

	def arch_chroot(
		self,
		cmd: str | list[str],
		run_as: str | None = None,
		peek_output: bool = False,
	) -> SysCommand | subprocess.CompletedProcess[bytes]:
		# argv list form avoids argv/shell-injection when arguments come from user or config input.
		if isinstance(cmd, list):
			if run_as:
				cmd = ['su', '-', run_as, '-c', shlex.join(cmd)]
			argv = cmd if self.target == Path('/') else ['arch-chroot', '-S', str(self.target), *cmd]
			return run(argv)

		if run_as:
			cmd = f'su - {run_as} -c {shlex.quote(cmd)}'

		return self.run_command(cmd, peek_output=peek_output)

	def drop_to_shell(self) -> None:
		subprocess.check_call(f'arch-chroot {self.target}', shell=True)

	def configure_nic(self, nic: Nic) -> None:
		conf = nic.as_systemd_config()

		with open(f'{self.target}/etc/systemd/network/10-{nic.iface}.network', 'a') as netconf:
			netconf.write(str(conf))

	def copy_iso_network_config(self, enable_services: bool = False) -> bool:
		# Copy (if any) iwd password and config files
		iwd_dir = LPath('/var/lib/iwd')
		if psk_files := list(iwd_dir.glob('*.psk')):
			iwd_target = self.target / iwd_dir.relative_to_root()
			iwd_target.mkdir(parents=True, exist_ok=True)

			for psk in psk_files:
				psk.copy(iwd_target / psk.name, preserve_metadata=True)

			if enable_services:
				# If we haven't installed the base yet (function called pre-maturely)
				if self._helper_flags.get('base', False) is False:
					self._base_packages.append('iwd')

					# This function will be called after minimal_installation()
					# as a hook for post-installs. This hook is only needed if
					# base is not installed yet.
					def post_install_enable_iwd_service(*args: str, **kwargs: str) -> None:
						self.enable_service('iwd')

					self.post_base_install.append(post_install_enable_iwd_service)
				# Otherwise, we can go ahead and add the required package
				# and enable it's service:
				else:
					self.pacman.strap('iwd')
					self.enable_service('iwd')

		# Enable systemd-resolved by (forcefully) setting a symlink
		# For further details see  https://wiki.archlinux.org/title/Systemd-resolved#DNS
		resolv_config_path = self.target / 'etc/resolv.conf'
		resolv_config_path.unlink(missing_ok=True)
		resolv_config_path.symlink_to('/run/systemd/resolve/stub-resolv.conf')

		# Copy (if any) systemd-networkd config files
		network_dir = LPath('/etc/systemd/network')
		if netconfigurations := list(network_dir.glob('*')):
			network_target = self.target / network_dir.relative_to_root()
			network_target.mkdir(parents=True, exist_ok=True)

			for netconf_file in netconfigurations:
				netconf_file.copy(network_target / netconf_file.name, preserve_metadata=True)

			if enable_services:
				# If we haven't installed the base yet (function called pre-maturely)
				if self._helper_flags.get('base', False) is False:

					def post_install_enable_networkd_resolved(*args: str, **kwargs: str) -> None:
						self.enable_service(['systemd-networkd', 'systemd-resolved'])

					self.post_base_install.append(post_install_enable_networkd_resolved)
				# Otherwise, we can go ahead and enable the services
				else:
					self.enable_service(['systemd-networkd', 'systemd-resolved'])

		return True

	def configure_nm_iwd(self) -> None:
		# Create NetworkManager config directory and write iwd backend conf
		nm_conf_dir = self.target / 'etc/NetworkManager/conf.d'
		nm_conf_dir.mkdir(parents=True, exist_ok=True)

		iwd_backend_conf = nm_conf_dir / 'wifi_backend.conf'
		iwd_backend_conf.write_text('[device]\nwifi.backend=iwd\n')

	def mkinitcpio(self, flags: list[str]) -> bool:
		with open(f'{self.target}/etc/mkinitcpio.conf', 'r+') as mkinit:
			content = mkinit.read()
			content = re.sub('\nMODULES=(.*)', f'\nMODULES=({" ".join(self._modules)})', content)
			content = re.sub('\nBINARIES=(.*)', f'\nBINARIES=({" ".join(self._binaries)})', content)
			content = re.sub('\nFILES=(.*)', f'\nFILES=({" ".join(self._files)})', content)
			content = re.sub('\nHOOKS=(.*)', f'\nHOOKS=({" ".join(self._hooks)})', content)
			mkinit.seek(0)
			mkinit.truncate()
			mkinit.write(content)

		try:
			self.arch_chroot(f'mkinitcpio {" ".join(flags)}', peek_output=True)
			return True
		except SysCallError as e:
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
			self._base_packages.append('bcachefs-dkms')
			self._base_packages.append('xxhash')

		# https://github.com/archlinux/archinstall/issues/1837
		# https://github.com/koverstreet/bcachefs/issues/916
		if fs_type.fs_type_mount in ('btrfs', 'bcachefs'):
			self._disable_fstrim = True

		if fs_type == FilesystemType.BCACHEFS:
			if 'bcachefs' not in self._modules:
				self._modules.append('bcachefs')
			if 'bcachefs' not in self._hooks and 'block' in self._hooks:
				self._hooks.insert(self._hooks.index('block') + 1, 'bcachefs')

		# There is not yet an fsck tool for NTFS. If it's being used for the root filesystem, the hook should be removed.
		if fs_type.fs_type_mount == 'ntfs3' and mountpoint == self.target and 'fsck' in self._hooks:
			self._hooks.remove('fsck')

	def _prepare_encrypt(self, before: str = 'filesystems') -> None:
		if 'sd-encrypt' not in self._hooks:
			self._hooks.insert(self._hooks.index(before), 'sd-encrypt')

	def minimal_installation(
		self,
		optional_repositories: list[Repository] = [],
		mkinitcpio: bool = True,
		hostname: str | None = None,
		locale_config: LocaleConfiguration | None = LocaleConfiguration.default(),
		timezone: str | None = None,
	) -> None:
		if self._disk_config.lvm_config:
			lvm = 'lvm2'
			self.add_additional_packages(lvm)
			self._hooks.insert(self._hooks.index('filesystems') - 1, lvm)

			for vg in self._disk_config.lvm_config.vol_groups:
				for vol in vg.volumes:
					if vol.fs_type is not None:
						self._prepare_fs_type(vol.fs_type, vol.mountpoint)

			types = (EncryptionType.LVM_ON_LUKS, EncryptionType.LUKS_ON_LVM)
			if self._disk_encryption.encryption_type in types:
				self._prepare_encrypt(lvm)
		else:
			for mod in self._disk_config.device_modifications:
				for part in mod.partitions:
					if part.fs_type is None:
						continue

					self._prepare_fs_type(part.fs_type, part.mountpoint)

					if part in self._disk_encryption.partitions:
						self._prepare_encrypt()

		if ucode := self._get_microcode():
			(self.target / 'boot' / ucode).unlink(missing_ok=True)
			self._base_packages.append(ucode.stem)
		else:
			debug('Archinstoo will not install any ucode.')

		debug(f'Optional repositories: {optional_repositories}')

		# This action takes place on the host system as pacstrap copies over package repository lists.
		pacman_conf = PacmanConfig(self.target)
		pacman_conf.enable(optional_repositories)
		pacman_conf.apply()

		if locale_config:
			self.set_vconsole(locale_config)
			# fonts that are in the ISO but wont be on target
			# unless we specifically request it before base
			# otherwise mkinitcpio will be screaming at you
			if locale_config.console_font.startswith('ter-'):
				self._base_packages.append('terminus-font')

		self.pacman.strap(list(dict.fromkeys(self._base_packages)))
		self._helper_flags['base-strapped'] = True

		pacman_conf.persist()

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

		if locale_config:
			self.set_locale(locale_config)

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
			function(self)

	def setup_btrfs_snapshot(
		self,
		snapshot_type: SnapshotType,
		bootloader: Bootloader | None = None,
	) -> None:
		if snapshot_type == SnapshotType.Snapper:
			debug('Setting up Btrfs snapper')
			self.pacman.strap('snapper')

			snapper: dict[str, str] = {
				'root': '/',
				'home': '/home',
			}

			for config_name, mountpoint in snapper.items():
				command = [
					'arch-chroot',
					'-S',
					str(self.target),
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
					raise DiskError(f'Could not setup Btrfs snapper: {err}')

			self.enable_service('snapper-timeline.timer')
			self.enable_service('snapper-cleanup.timer')

		elif snapshot_type == SnapshotType.Timeshift:
			debug('Setting up Btrfs timeshift')

			self.pacman.strap('cronie')
			self.pacman.strap('timeshift')
			self.enable_service('cronie')

		if bootloader and bootloader == Bootloader.Grub:
			debug('Setting up grub integration for either')
			self.pacman.strap('grub-btrfs')
			self.pacman.strap('inotify-tools')
			self._configure_grub_btrfsd(snapshot_type)
			self.enable_service('grub-btrfsd')

	def setup_swap(
		self,
		kind: str = 'zram',
		algo: ZramAlgorithm = ZramAlgorithm.Default,
		recomp_algo: ZramAlgorithm | None = None,
	) -> None:
		if kind == 'zram':
			info('Setting up swap on zram')
			self.pacman.strap('zram-generator')

			with open(f'{self.target}/etc/systemd/zram-generator.conf', 'w') as zram_conf:
				zram_conf.write('[zram0]\n')
				zram_conf.write('zram-size = ram / 2\n')
				if algo != ZramAlgorithm.Default:
					comp_line = algo.value
					if recomp_algo:
						comp_line += f' {recomp_algo.value} (type=idle)'
					zram_conf.write(f'compression-algorithm = {comp_line}\n')

			self.enable_service('systemd-zram-setup@zram0')

			self._zram_enabled = True
		else:
			raise ValueError('Archinstoo currently only supports setting up swap on zram')

	def setup_sysctl(self, entries: list[str]) -> None:
		if not entries:
			return

		info('Writing sysctl configuration')
		sysctl_dir = self.target / 'etc/sysctl.d'
		sysctl_dir.mkdir(parents=True, exist_ok=True)

		conf = sysctl_dir / '99-archinstoo.conf'
		conf.write_text('\n'.join(entries) + '\n')

	def _get_efi_partition(self) -> PartitionModification | None:
		for layout in self._disk_config.device_modifications:
			if partition := layout.get_efi_partition():
				return partition
		return None

	def _get_boot_partition(self) -> PartitionModification | None:
		for layout in self._disk_config.device_modifications:
			if boot := layout.get_boot_partition():
				return boot
		return None

	def _get_root(self) -> PartitionModification | LvmVolume | None:
		if self._disk_config.lvm_config:
			return self._disk_config.lvm_config.get_root_volume()
		for mod in self._disk_config.device_modifications:
			if root := mod.get_root_partition():
				return root
		return None

	def _configure_grub_btrfsd(self, snapshot_type: SnapshotType) -> None:
		if snapshot_type == SnapshotType.Timeshift:
			snapshot_path = '--timeshift-auto'
		elif snapshot_type == SnapshotType.Snapper:
			snapshot_path = '/.snapshots'
		else:
			raise ValueError('Unsupported snapshot type')

		debug(f'Configuring grub-btrfsd service for {snapshot_type} at {snapshot_path}')

		# Works for either snapper or ts just adapting default paths above
		# https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html#id-1.14.3
		systemd_dir = self.target / 'etc/systemd/system/grub-btrfsd.service.d'
		systemd_dir.mkdir(parents=True, exist_ok=True)

		override_conf = systemd_dir / 'override.conf'

		config_content = textwrap.dedent(
			"""
			[Service]
			ExecStart=
			ExecStart=/usr/bin/grub-btrfsd --syslog {snapshot_path}
			"""
		).format(snapshot_path=snapshot_path)

		override_conf.write_text(config_content)
		override_conf.chmod(0o644)

	def _get_luks_uuid_from_mapper_dev(self, mapper_dev_path: Path) -> str:
		lsblk_info = get_lsblk_info(mapper_dev_path, reverse=True, full_dev_path=True)

		if not lsblk_info.children or not lsblk_info.children[0].uuid:
			raise ValueError('Unable to determine UUID of luks superblock')

		return lsblk_info.children[0].uuid

	def _get_kernel_params_partition(
		self,
		root_partition: PartitionModification,
		id_root: bool = True,
		partuuid: bool = True,
	) -> list[str]:
		kernel_parameters = []

		if root_partition in self._disk_encryption.partitions:
			debug(f'Root partition is an encrypted device, identifying by UUID: {root_partition.uuid}')
			kernel_parameters.append(f'rd.luks.name={root_partition.uuid}=root')

			if id_root:
				kernel_parameters.append('root=/dev/mapper/root')
		elif id_root:
			if partuuid:
				debug(f'Identifying root partition by PARTUUID: {root_partition.partuuid}')
				kernel_parameters.append(f'root=PARTUUID={root_partition.partuuid}')
			else:
				debug(f'Identifying root partition by UUID: {root_partition.uuid}')
				kernel_parameters.append(f'root=UUID={root_partition.uuid}')

		return kernel_parameters

	def _get_kernel_params_lvm(
		self,
		lvm: LvmVolume,
	) -> list[str]:
		kernel_parameters = []

		match self._disk_encryption.encryption_type:
			case EncryptionType.LVM_ON_LUKS:
				if not lvm.vg_name:
					raise ValueError(f'Unable to determine VG name for {lvm.name}')

				pv_seg_info = lvm_pvseg_info(lvm.vg_name, lvm.name)

				if not pv_seg_info:
					raise ValueError(f'Unable to determine PV segment info for {lvm.vg_name}/{lvm.name}')

				uuid = self._get_luks_uuid_from_mapper_dev(pv_seg_info.pv_name)

				debug(f'LvmOnLuks, encrypted root partition, identifying by UUID: {uuid}')
				kernel_parameters.append(f'rd.luks.name={uuid}=cryptlvm root={lvm.safe_dev_path}')
			case EncryptionType.LUKS_ON_LVM:
				uuid = self._get_luks_uuid_from_mapper_dev(lvm.mapper_path)

				debug(f'LuksOnLvm, encrypted root partition, identifying by UUID: {uuid}')
				kernel_parameters.append(f'rd.luks.name={uuid}=root root=/dev/mapper/root')
			case EncryptionType.NO_ENCRYPTION:
				debug(f'Identifying root lvm by mapper device: {lvm.dev_path}')
				kernel_parameters.append(f'root={lvm.safe_dev_path}')

		return kernel_parameters

	def _get_kernel_params(
		self,
		root: PartitionModification | LvmVolume,
		id_root: bool = True,
		partuuid: bool = True,
	) -> list[str]:
		kernel_parameters = []

		kernel_parameters = self._get_kernel_params_lvm(root) if isinstance(root, LvmVolume) else self._get_kernel_params_partition(root, id_root, partuuid)

		# Zswap should be disabled when using zram.
		# https://github.com/archlinux/archinstall/issues/881
		if self._zram_enabled:
			kernel_parameters.append('zswap.enabled=0')

		if self._disk_encryption.tpm2_unlock and self._disk_encryption.encryption_type != EncryptionType.NO_ENCRYPTION:
			kernel_parameters.append('rd.luks.options=tpm2-device=auto')

		if id_root:
			for sub_vol in root.btrfs_subvols:
				if sub_vol.is_root():
					kernel_parameters.append(f'rootflags=subvol={sub_vol.name}')
					break

			kernel_parameters.append('rw')

		kernel_parameters.append(f'rootfstype={root.safe_fs_type.fs_type_mount}')
		kernel_parameters.extend(self._kernel_params)

		debug(f'kernel parameters: {" ".join(kernel_parameters)}')

		return kernel_parameters

	def _create_bls_entries(
		self,
		boot_partition: PartitionModification,
		root: PartitionModification | LvmVolume,
		entry_name: str,
	) -> None:
		# Loader entries are stored in $BOOT/loader:
		# https://uapi-group.org/specifications/specs/boot_loader_specification/#mount-points
		entries_dir = self.target / boot_partition.relative_mountpoint / 'loader/entries'
		# Ensure that the $BOOT/loader/entries/ directory exists before trying to create files in it
		entries_dir.mkdir(parents=True, exist_ok=True)

		entry_template = textwrap.dedent(
			f"""\
			# Created by: archinstoo
			title   Arch Linux ({{kernel}})
			linux   /vmlinuz-{{kernel}}
			initrd  /initramfs-{{kernel}}.img
			options {' '.join(self._get_kernel_params(root))}
			""",
		)

		for kernel in self.kernels:
			# Setup the loader entry
			name = entry_name.format(kernel=kernel)
			entry_conf = entries_dir / name
			entry_conf.write_text(entry_template.format(kernel=kernel))

	def _add_systemd_bootloader(
		self,
		boot_partition: PartitionModification,
		root: PartitionModification | LvmVolume,
		efi_partition: PartitionModification | None,
		uki_enabled: bool = False,
	) -> None:
		debug('Installing systemd bootloader')

		self.pacman.strap('efibootmgr')

		if not SysInfo.has_uefi():
			raise HardwareIncompatibilityError

		if not efi_partition:
			raise ValueError('Could not detect EFI system partition')
		if not efi_partition.mountpoint:
			raise ValueError('EFI system partition is not mounted')

		# TODO: Ideally we would want to check if another config
		# points towards the same disk and/or partition.
		# And in which case we should do some clean up.
		bootctl_options = []

		if boot_partition != efi_partition:
			bootctl_options.append(f'--esp-path={efi_partition.mountpoint}')
			bootctl_options.append(f'--boot-path={boot_partition.mountpoint}')

		# TODO: This is a temporary workaround to deal with https://github.com/archlinux/archinstall/pull/3396#issuecomment-2996862019
		# the systemd_version check can be removed once `--variables=BOOL` is merged into systemd.
		# keep the version as a str as it can be something like 257.8-2
		if (systemd_pkg := installed_package('systemd')) is not None:
			systemd_version = systemd_pkg.version
		else:
			systemd_version = '257'  # This works as a safety workaround for this hot-fix

		try:
			# Force EFI variables since bootctl detects arch-chroot
			# as a container environment since v257 and skips them silently.
			# https://github.com/systemd/systemd/issues/36174
			if systemd_version >= '258':
				self.arch_chroot(f'bootctl --variables=yes {" ".join(bootctl_options)} install')
			else:
				self.arch_chroot(f'bootctl {" ".join(bootctl_options)} install')
		except SysCallError:
			if systemd_version >= '258':
				# Fallback, try creating the boot loader without touching the EFI variables
				self.arch_chroot(f'bootctl --variables=no {" ".join(bootctl_options)} install')
			else:
				self.arch_chroot(f'bootctl --no-variables {" ".join(bootctl_options)} install')

		# Loader configuration is stored in ESP/loader:
		# https://man.archlinux.org/man/loader.conf.5
		loader_conf = self.target / efi_partition.relative_mountpoint / 'loader/loader.conf'
		# Ensure that the ESP/loader/ directory exists before trying to create a file in it
		loader_conf.parent.mkdir(parents=True, exist_ok=True)

		default_kernel = self.kernels[0]
		if uki_enabled:
			default_entry = f'arch-{default_kernel}.efi'
		else:
			entry_name = 'arch_{kernel}.conf'
			default_entry = entry_name.format(kernel=default_kernel)
			self._create_bls_entries(boot_partition, root, entry_name)

		default = f'default {default_entry}'

		# Modify or create a loader.conf
		try:
			loader_data = loader_conf.read_text().splitlines()
		except FileNotFoundError:
			loader_data = [
				default,
				'timeout 15',
			]
		else:
			for index, line in enumerate(loader_data):
				if line.startswith('default'):
					loader_data[index] = default
				elif line.startswith('#timeout'):
					# We add in the default timeout to support dual-boot
					loader_data[index] = line.removeprefix('#')

		loader_conf.write_text('\n'.join(loader_data) + '\n')

		self._helper_flags['bootloader'] = 'systemd'

	def _add_grub_bootloader(
		self,
		boot_partition: PartitionModification,
		root: PartitionModification | LvmVolume,
		efi_partition: PartitionModification | None,
		uki_enabled: bool = False,
		bootloader_removable: bool = False,
	) -> None:
		debug('Installing grub bootloader')

		self.pacman.strap('grub')

		# enable GRUB cryptodisk before grub-install so crypto modules
		# are embedded in the core image (required for encrypted /boot)
		grub_default = self.target / 'etc/default/grub'
		if self._disk_encryption.encryption_type != EncryptionType.NO_ENCRYPTION:
			config = grub_default.read_text()
			config = re.sub(r'^#(GRUB_ENABLE_CRYPTODISK=y)', r'\1', config, flags=re.MULTILINE)
			grub_default.write_text(config)

		info(f'GRUB boot partition: {boot_partition.dev_path}')

		boot_dir = Path('/boot')

		command = [
			'arch-chroot',
			'-S',
			str(self.target),
			'grub-install',
			'--debug',
		]

		if SysInfo.has_uefi():
			if not efi_partition:
				raise ValueError('Could not detect efi partition')

			info(f'GRUB EFI partition: {efi_partition.dev_path}')

			self.pacman.strap('efibootmgr')  # TODO: Do we need? Yes, but remove from minimal_installation() instead?

			boot_dir_arg = []
			if boot_partition.mountpoint and boot_partition.mountpoint != boot_dir:
				boot_dir_arg.append(f'--boot-directory={boot_partition.mountpoint}')
				boot_dir = boot_partition.mountpoint

			grub_target = 'x86_64-efi' if SysInfo._bitness() == 64 else 'i386-efi'
			# https://wiki.archlinux.org/title/Unified_Extensible_Firmware_Interface
			# mixed mode boot handling same as limine handling 32bit UEFI on 64-bit CPUs

			add_options = [
				f'--target={grub_target}',
				f'--efi-directory={efi_partition.mountpoint}',
				*boot_dir_arg,
				'--bootloader-id=GRUB',
			]

			if bootloader_removable:
				add_options.append('--removable')

			command.extend(add_options)

			try:
				SysCommand(command, peek_output=True)
			except SysCallError as err:
				raise DiskError(f'Could not install GRUB to {self.target}{efi_partition.mountpoint}: {err}')
		else:
			info(f'GRUB boot partition: {boot_partition.dev_path}')

			parent_dev_path = get_parent_device_path(boot_partition.safe_dev_path)

			add_options = [
				'--target=i386-pc',
				'--recheck',
				str(parent_dev_path),
			]

			try:
				SysCommand(command + add_options, peek_output=True)
			except SysCallError as err:
				raise DiskError(f'Failed to install GRUB boot on {boot_partition.dev_path}: {err}')

		if SysInfo.has_uefi() and uki_enabled:
			grub_d = LPath(self.target) / 'etc/grub.d'
			linux_file = grub_d / '10_linux'
			uki_file = grub_d / '15_uki'

			raw_str_platform = r'\$grub_platform'
			space_indent_cmd = '  uki'
			content = textwrap.dedent(
				f"""\
				#! /bin/sh
				set -e

				cat << EOF
				if [ "{raw_str_platform}" = "efi" ]; then
				{space_indent_cmd}
				fi
				EOF
				""",
			)

			try:
				uki_file.write_text(content)
				uki_file.add_exec()
				linux_file.remove_exec()
			except OSError:
				error('Failed to enable UKI menu entries')
		else:
			config = grub_default.read_text()

			kernel_parameters = ' '.join(
				self._get_kernel_params(root, id_root=False, partuuid=False),
			)
			config = re.sub(
				r'^(GRUB_CMDLINE_LINUX=")(")$',
				rf'\1{kernel_parameters}\2',
				config,
				count=1,
				flags=re.MULTILINE,
			)

			grub_default.write_text(config)

		try:
			self.arch_chroot(
				f'grub-mkconfig -o {boot_dir}/grub/grub.cfg',
			)
		except SysCallError as err:
			raise DiskError(f'Could not configure GRUB: {err}')

		self._helper_flags['bootloader'] = 'grub'

	def _add_limine_bootloader(
		self,
		boot_partition: PartitionModification,
		efi_partition: PartitionModification | None,
		root: PartitionModification | LvmVolume,
		uki_enabled: bool = False,
		bootloader_removable: bool = False,
	) -> None:
		debug('Installing Limine bootloader')

		self.pacman.strap('limine')

		info(f'Limine boot partition: {boot_partition.dev_path}')

		limine_path = self.target / 'usr' / 'share' / 'limine'
		config_path = None
		hook_command = None

		if SysInfo.has_uefi():
			self.pacman.strap('efibootmgr')

			if not efi_partition:
				raise ValueError('Could not detect efi partition')
			if not efi_partition.mountpoint:
				raise ValueError('EFI partition is not mounted')

			info(f'Limine EFI partition: {efi_partition.dev_path}')

			parent_dev_path = get_parent_device_path(efi_partition.safe_dev_path)

			try:
				efi_dir_path = self.target / efi_partition.mountpoint.relative_to('/') / 'EFI'
				efi_dir_path_target = efi_partition.mountpoint / 'EFI'
				subdir = 'BOOT' if bootloader_removable else 'arch-limine'
				efi_dir_path = efi_dir_path / subdir
				efi_dir_path_target = efi_dir_path_target / subdir
				config_path = efi_dir_path / 'limine.conf'

				efi_dir_path.mkdir(parents=True, exist_ok=True)

				for file in ('BOOTIA32.EFI', 'BOOTX64.EFI'):
					(limine_path / file).copy_into(efi_dir_path)
			except Exception as err:
				raise DiskError(f'Failed to install Limine in {self.target}{efi_partition.mountpoint}: {err}')

			hook_command = (
				f'/usr/bin/cp /usr/share/limine/BOOTIA32.EFI {efi_dir_path_target}/ && /usr/bin/cp /usr/share/limine/BOOTX64.EFI {efi_dir_path_target}/'
			)

			if not bootloader_removable:
				# Create EFI boot menu entry for Limine.
				try:
					# see https://wiki.archlinux.org/title/Arch_boot_process
					# mixed mode booting (32bit UEFI on x86_64 CPU)
					efi_bitness = SysInfo._bitness()
				except Exception as err:
					raise OSError(f'Could not open or read /sys/ to determine EFI bitness: {err}')

				if efi_bitness == 64:
					loader_path = '\\EFI\\arch-limine\\BOOTX64.EFI'
				elif efi_bitness == 32:
					loader_path = '\\EFI\\arch-limine\\BOOTIA32.EFI'
				else:
					raise ValueError(f'EFI bitness is neither 32 nor 64 bits. Found "{efi_bitness}".')

				try:
					SysCommand(
						'efibootmgr'
						' --create'
						f' --disk {parent_dev_path}'
						f' --part {efi_partition.partn}'
						' --label "Arch Linux Limine Bootloader"'
						f" --loader '{loader_path}'"
						' --unicode'
						' --verbose',
					)
				except Exception as err:
					raise ValueError(f'SysCommand for efibootmgr failed: {err}')
		else:
			boot_limine_path = self.target / 'boot' / 'limine'
			boot_limine_path.mkdir(parents=True, exist_ok=True)

			config_path = boot_limine_path / 'limine.conf'

			parent_dev_path = get_parent_device_path(boot_partition.safe_dev_path)

			if unique_path := self._device_handler.get_unique_path_for_device(parent_dev_path):
				parent_dev_path = unique_path

			try:
				# The `limine-bios.sys` file contains stage 3 code.
				(limine_path / 'limine-bios.sys').copy_into(boot_limine_path)

				# `limine bios-install` deploys the stage 1 and 2 to the
				self.arch_chroot(f'limine bios-install {parent_dev_path}', peek_output=True)
			except Exception as err:
				raise DiskError(f'Failed to install Limine on {parent_dev_path}: {err}')

			hook_command = f'/usr/bin/limine bios-install {parent_dev_path} && /usr/bin/cp /usr/share/limine/limine-bios.sys /boot/limine/'

		hook_contents = textwrap.dedent(
			f'''\
			[Trigger]
			Operation = Install
			Operation = Upgrade
			Type = Package
			Target = limine

			[Action]
			Description = Deploying Limine after upgrade...
			When = PostTransaction
			Exec = /bin/sh -c "{hook_command}"
			''',
		)

		hooks_dir = self.target / 'etc' / 'pacman.d' / 'hooks'
		hooks_dir.mkdir(parents=True, exist_ok=True)

		hook_path = hooks_dir / '99-limine.hook'
		hook_path.write_text(hook_contents)

		kernel_params = ' '.join(self._get_kernel_params(root))
		config_contents = 'timeout: 5\n'

		path_root = 'boot()'
		if efi_partition:
			if boot_partition != efi_partition:
				path_root = f'uuid({boot_partition.partuuid})'
			elif efi_partition.mountpoint != Path('/boot') and isinstance(root, PartitionModification):
				path_root = f'uuid({root.partuuid})'

		for kernel in self.kernels:
			if uki_enabled:
				entry = [
					'protocol: efi',
					f'path: boot():/EFI/Linux/arch-{kernel}.efi',
					f'cmdline: {kernel_params}',
				]
				config_contents += f'\n/Arch Linux ({kernel})\n'
				config_contents += '\n'.join(f'    {it}' for it in entry) + '\n'
			else:
				entry = [
					'protocol: linux',
					f'path: {path_root}:/vmlinuz-{kernel}',
					f'cmdline: {kernel_params}',
					f'module_path: {path_root}:/initramfs-{kernel}.img',
				]
				config_contents += f'\n/Arch Linux ({kernel})\n'
				config_contents += '\n'.join(f'    {it}' for it in entry) + '\n'

		config_path.write_text(config_contents)

		self._helper_flags['bootloader'] = 'limine'

	def _add_efistub_bootloader(
		self,
		boot_partition: PartitionModification,
		root: PartitionModification | LvmVolume,
		uki_enabled: bool = False,
	) -> None:
		debug('Installing efistub bootloader')

		self.pacman.strap('efibootmgr')

		if not SysInfo.has_uefi():
			raise HardwareIncompatibilityError

		# TODO: Ideally we would want to check if another config
		# points towards the same disk and/or partition.
		# And in which case we should do some clean up.

		if not uki_enabled:
			loader = '/vmlinuz-{kernel}'
			# EFI standards stipulate backslashes
			entries = (
				r'initrd=\initramfs-{kernel}.img',
				*self._get_kernel_params(root),
			)

			cmdline = [' '.join(entries)]
		else:
			loader = '/EFI/Linux/arch-{kernel}.efi'
			cmdline = []

		parent_dev_path = get_parent_device_path(boot_partition.safe_dev_path)

		cmd_template = (
			'efibootmgr',
			'--create',
			'--disk',
			str(parent_dev_path),
			'--part',
			str(boot_partition.partn),
			'--label',
			'Arch Linux ({kernel})',
			'--loader',
			loader,
			'--unicode',
			*cmdline,
			'--verbose',
		)

		for kernel in self.kernels:
			# Setup the firmware entry
			cmd = [arg.format(kernel=kernel) for arg in cmd_template]
			SysCommand(cmd)

		self._helper_flags['bootloader'] = 'efistub'

	def _add_refind_bootloader(
		self,
		boot_partition: PartitionModification,
		efi_partition: PartitionModification | None,
		root: PartitionModification | LvmVolume,
		uki_enabled: bool = False,
	) -> None:
		debug('Installing rEFInd bootloader')

		self.pacman.strap('refind')

		if not SysInfo.has_uefi():
			raise HardwareIncompatibilityError

		info(f'rEFInd boot partition: {boot_partition.dev_path}')

		if not efi_partition:
			raise ValueError('Could not detect EFI system partition')
		if not efi_partition.mountpoint:
			raise ValueError('EFI system partition is not mounted')

		info(f'rEFInd EFI partition: {efi_partition.dev_path}')

		try:
			self.arch_chroot('refind-install')
		except SysCallError as err:
			raise DiskError(f'Could not install rEFInd to {self.target}{efi_partition.mountpoint}: {err}')

		if not boot_partition.mountpoint:
			raise ValueError('Boot partition is not mounted, cannot write rEFInd config')

		boot_is_separate = boot_partition != efi_partition and boot_partition.dev_path != efi_partition.dev_path

		if boot_is_separate:
			# Separate boot partition (not ESP, not root)
			config_path = self.target / boot_partition.mountpoint.relative_to('/') / 'refind_linux.conf'
			boot_on_root = False
		elif efi_partition.mountpoint == Path('/boot'):
			# ESP is mounted at /boot, kernels are on ESP
			config_path = self.target / 'boot' / 'refind_linux.conf'
			boot_on_root = False
		else:
			# ESP is elsewhere (/efi, /boot/efi, etc.), kernels are on root filesystem at /boot
			config_path = self.target / 'boot' / 'refind_linux.conf'
			boot_on_root = True

		config_contents = []

		kernel_params = ' '.join(self._get_kernel_params(root))

		for kernel in self.kernels:
			if uki_enabled:
				entry = f'"Arch Linux ({kernel}) UKI" "{kernel_params}"'
			else:
				if boot_on_root:
					# Kernels are in /boot subdirectory of root filesystem
					if hasattr(root, 'btrfs_subvols') and root.btrfs_subvols:
						# Root is btrfs with subvolume, find the root subvolume
						root_subvol = next((sv for sv in root.btrfs_subvols if sv.is_root()), None)
						if root_subvol:
							subvol_name = root_subvol.name
							initrd_path = f'initrd={subvol_name}\\boot\\initramfs-{kernel}.img'
						else:
							initrd_path = f'initrd=\\boot\\initramfs-{kernel}.img'
					else:
						# Root without btrfs subvolume
						initrd_path = f'initrd=\\boot\\initramfs-{kernel}.img'
				else:
					# Kernels are at root of their partition (ESP or separate boot partition)
					initrd_path = f'initrd=\\initramfs-{kernel}.img'
				entry = f'"Arch Linux ({kernel})" "{kernel_params} {initrd_path}"'

			config_contents.append(entry)

		config_path.write_text('\n'.join(config_contents) + '\n')

		hook_contents = textwrap.dedent(
			"""\
			[Trigger]
			Operation = Install
			Operation = Upgrade
			Type = Package
			Target = refind

			[Action]
			Description = Updating rEFInd on ESP
			When = PostTransaction
			Exec = /usr/bin/refind-install
			"""
		)

		hooks_dir = self.target / 'etc' / 'pacman.d' / 'hooks'
		hooks_dir.mkdir(parents=True, exist_ok=True)

		hook_path = hooks_dir / '99-refind.hook'
		hook_path.write_text(hook_contents)

		self._helper_flags['bootloader'] = 'refind'

	def _config_uki(
		self,
		root: PartitionModification | LvmVolume,
		efi_partition: PartitionModification | None,
	) -> None:
		if not efi_partition or not efi_partition.mountpoint:
			raise ValueError(f'Could not detect ESP at mountpoint {self.target}')

		# Set up kernel command line
		with open(self.target / 'etc/kernel/cmdline', 'w') as cmdline:
			kernel_parameters = self._get_kernel_params(root)
			cmdline.write(' '.join(kernel_parameters) + '\n')

		diff_mountpoint = None

		if efi_partition.mountpoint != Path('/efi'):
			diff_mountpoint = str(efi_partition.mountpoint)

		image_re = re.compile('(.+_image="/([^"]+).+\n)')
		uki_re = re.compile('#((.+_uki=")/[^/]+(.+\n))')

		# Per-kernel os-release so GRUB UKI entries show the kernel variant
		osrelease_dir = self.target / 'etc/os-release.d'
		osrelease_dir.mkdir(parents=True, exist_ok=True)
		base_osrelease = (self.target / 'etc/os-release').read_text()

		# Modify .preset files
		for kernel in self.kernels:
			kernel_osrelease = re.sub(
				r'^PRETTY_NAME=".*"',
				f'PRETTY_NAME="Arch Linux ({kernel})"',
				base_osrelease,
				count=1,
				flags=re.MULTILINE,
			)
			(osrelease_dir / kernel).write_text(kernel_osrelease)

			preset = self.target / 'etc/mkinitcpio.d' / (kernel + '.preset')
			config = preset.read_text().splitlines(True)

			for index, line in enumerate(config):
				# Avoid storing redundant image file
				if m := image_re.match(line):
					image = self.target / m.group(2)
					image.unlink(missing_ok=True)
					config[index] = '#' + m.group(1)
				elif m := uki_re.match(line):
					if diff_mountpoint:
						config[index] = m.group(2) + diff_mountpoint + m.group(3)
					else:
						config[index] = m.group(1)
				elif line.startswith('#default_options='):
					config[index] = line.removeprefix('#').rstrip('\n').rstrip('"') + f' --osrelease /etc/os-release.d/{kernel}"\n'

			preset.write_text(''.join(config))

		# Directory for the UKIs
		uki_dir = self.target / efi_partition.relative_mountpoint / 'EFI/Linux'
		uki_dir.mkdir(parents=True, exist_ok=True)

		# Build the UKIs
		if not self.mkinitcpio(['-P']):
			error('Error generating initramfs (continuing anyway)')

	def _flip_bmp(self, path: Path) -> None:
		if not path.exists():
			return
		data = bytearray(path.read_bytes())
		offset = int.from_bytes(data[10:14], 'little')
		width = int.from_bytes(data[18:22], 'little')
		height = abs(int.from_bytes(data[22:26], 'little', signed=True))
		row_size = ((width * int.from_bytes(data[28:30], 'little') + 31) // 32) * 4
		rows = [data[offset + i * row_size : offset + (i + 1) * row_size] for i in range(height)]
		data[offset:] = b''.join(reversed(rows))
		path.write_bytes(data)

	def add_bootloader(self, bootloader: Bootloader, uki_enabled: bool = False, bootloader_removable: bool = False) -> None:
		"""
		Adds a bootloader to the installation instance.
		Archinstoo supports one of five types:
		* systemd-bootctl
		* grub
		* limine
		* efistub
		* refind

		:param bootloader: Type of bootloader to be added
		:param uki_enabled: Whether to use unified kernel images
		:param bootloader_removable: Whether to install to removable media location (UEFI only, for GRUB and Limine)
		"""
		self._flip_bmp(self.target / 'usr/share/systemd/bootctl/splash-arch.bmp')

		# Run before bootloader install so kernel cmdline reflects rd.luks.options=tpm2-device=auto
		self.enroll_tpm2()

		efi_partition = self._get_efi_partition()
		boot_partition = self._get_boot_partition()
		root = self._get_root()

		if boot_partition is None:
			if SysInfo.has_uefi() and efi_partition is not None:
				boot_partition = efi_partition
			else:
				raise ValueError(f'Could not detect boot at mountpoint {self.target}')

		if root is None:
			raise ValueError(f'Could not detect root at mountpoint {self.target}')

		info(f'Adding bootloader {bootloader.value} to {boot_partition.dev_path}')

		# validate removable bootloader option
		if bootloader_removable:
			if not SysInfo.has_uefi():
				warn('Removable install requested but system is not UEFI; disabling.')
				bootloader_removable = False
			elif not bootloader.has_removable_support():
				warn(f'Bootloader {bootloader.value} lacks removable support; disabling.')
				bootloader_removable = False

		if uki_enabled:
			self._config_uki(root, efi_partition)

		match bootloader:
			case Bootloader.Systemd:
				self._add_systemd_bootloader(boot_partition, root, efi_partition, uki_enabled)
			case Bootloader.Grub:
				self._add_grub_bootloader(boot_partition, root, efi_partition, uki_enabled, bootloader_removable)
			case Bootloader.Efistub:
				self._add_efistub_bootloader(boot_partition, root, uki_enabled)
			case Bootloader.Limine:
				self._add_limine_bootloader(boot_partition, efi_partition, root, uki_enabled, bootloader_removable)
			case Bootloader.Refind:
				self._add_refind_bootloader(boot_partition, efi_partition, root, uki_enabled)

	def add_additional_packages(self, packages: str | list[str]) -> None:
		return self.pacman.strap(packages)

	def add_kernel_param(self, params: str | list[str]) -> None:
		if isinstance(params, str):
			params = [params]
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
			with open(self.target / 'etc/sudoers', 'a') as sudoers:
				sudoers.write('@includedir /etc/sudoers.d\n')

		# We count how many files are there already so we know which number to prefix the file with
		num_of_rules_already = len(os.listdir(sudoers_dir))
		file_num_str = f'{num_of_rules_already:02d}'  # We want 00_user1, 01_user2, etc

		# Guarantees that username str does not contain invalid characters for a linux file name:
		# \ / : * ? " < > |
		safe_username_file_name = re.sub(r'(\\|\/|:|\*|\?|"|<|>|\|)', '', user.username)

		rule_file = sudoers_dir / f'{file_num_str}_{safe_username_file_name}'

		with rule_file.open('a') as sudoers:
			sudoers.write(f'{"%" if group else ""}{user.username} ALL=(ALL) ALL\n')

		# Guarantees sudoer conf file recommended perms
		rule_file.chmod(0o440)

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
			return

		makepkg_conf = self.target / 'etc/makepkg.conf'
		if not makepkg_conf.exists():
			return

		content = makepkg_conf.read_text()
		content = content.replace('#PACMAN_AUTH=()', f'PACMAN_AUTH=({auth_binary})')
		makepkg_conf.write_text(content)

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

		self.add_additional_packages('git')

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
			self.arch_chroot(['chown', '-R', f'{username}:{username}', stash_dir])
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
		cmd = ['arch-chroot', '-S', str(self.target), 'chpasswd', '--encrypted']

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

	def chown(self, owner: str, path: str, options: list[str] | None = None) -> bool:
		options = options or []
		try:
			self.arch_chroot(['chown', *options, owner, path])
			return True
		except CalledProcessError as err:
			debug(f'Error changing ownership of {path}: {err}')
			return False

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

	def set_x11_keyboard(self, vconsole_layout: str) -> bool:
		"""Write X11 keyboard config directly for Xorg profiles."""
		if not vconsole_layout.strip():
			debug('X11 keyboard layout not specified, skipping')
			return False

		# Normalize vconsole layout to X11 format by stripping common suffixes
		layout = vconsole_layout
		for suffix in ('-latin1', '-latin2', '-latin9', '-nodeadkeys', '-mac'):
			layout = layout.removesuffix(suffix)
		# Handle compound suffixes like de-latin1-nodeadkeys
		for suffix in ('-latin1', '-latin2', '-latin9'):
			layout = layout.removesuffix(suffix)

		# Verify layout exists in target (where X11 is installed)
		try:
			layouts = self.run_command('localectl --no-pager list-x11-keymap-layouts').decode().splitlines()
			if not any(layout.lower() == x11_layout.lower() for x11_layout in layouts):
				debug(f'No matching X11 layout for vconsole "{vconsole_layout}", skipping')
				return False
		except Exception as e:
			debug(f'Could not verify X11 layout: {e}, proceeding anyway')
			# Proceed anyway if verification fails

		xorg_conf_dir = self.target / 'etc/X11/xorg.conf.d'
		xorg_conf_dir.mkdir(parents=True, exist_ok=True)

		content = f'''\
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "{layout}"
EndSection
'''

		(xorg_conf_dir / '00-keyboard.conf').write_text(content)
		info(f'Wrote X11 keyboard config with layout: {layout}')
		return True

	def _service_started(self, service_name: str) -> str | None:
		if os.path.splitext(service_name)[1] not in ('.service', '.target', '.timer'):
			service_name += '.service'  # Just to be safe

		last_execution_time = (
			SysCommand(
				f'systemctl show --property=ActiveEnterTimestamp --no-pager {service_name}',
				environment_vars={'SYSTEMD_COLORS': '0'},
			)
			.decode()
			.removeprefix('ActiveEnterTimestamp=')
		)

		if not last_execution_time:
			return None

		return last_execution_time

	def _service_state(self, service_name: str) -> str:
		if os.path.splitext(service_name)[1] not in ('.service', '.target', '.timer'):
			service_name += '.service'  # Just to be safe

		return SysCommand(
			f'systemctl show --no-pager -p SubState --value {service_name}',
			environment_vars={'SYSTEMD_COLORS': '0'},
		).decode()


def accessibility_tools_in_use() -> bool:
	return subprocess.run(['systemctl', 'is-active', '--quiet', 'espeakup.service'], check=False).returncode == 0


def run_aur_installation(packages: list[str], installation: Installer, users: list[User]) -> None:
	build_user = next((u for u in users if u.elev), None)

	if not build_user:
		warn('No elevated user found, skipping AUR packages')
		return

	installation.add_additional_packages(['base-devel', 'git'])

	grimaur_src = Path(__file__).parent / 'grimaur.py'
	grimaur_dest = installation.target / 'usr/local/bin/grimaur'
	grimaur_src.copy(grimaur_dest, preserve_metadata=True)
	grimaur_dest.chmod(0o755)

	# Temporary NOPASSWD for pacman so makepkg -si works without a tty
	sudoers_dir = installation.target / 'etc/sudoers.d'
	aur_rule = sudoers_dir / '99-aur-build'
	aur_rule.write_text(f'{build_user.username} ALL=(ALL) NOPASSWD: /usr/bin/pacman\n')
	aur_rule.chmod(0o440)

	try:
		for pkg in packages:
			info(f'Installing AUR package: {pkg}')
			try:
				installation.arch_chroot(
					f'grimaur --no-color install {shlex.quote(pkg)} --noconfirm',
					run_as=build_user.username,
					peek_output=True,
				)
			except SysCallError as e:
				warn(f'AUR package "{pkg}" failed: {e}')
	finally:
		aur_rule.unlink(missing_ok=True)


def run_custom_user_commands(commands: list[str], installation: Installer) -> None:
	for index, command in enumerate(commands):
		script_path = f'/var/tmp/user-command.{index}.sh'
		chroot_path = f'{installation.target}/{script_path}'

		# Do not throw error instead warn
		info(f'Executing custom command "{command}" ...')
		with open(chroot_path, 'w') as user_script:
			user_script.write(command)

		try:
			SysCommand(f'arch-chroot -S {installation.target} bash {script_path}')
		except SysCallError as e:
			warn(f'Custom command "{command}" failed: {e}')
		finally:
			os.unlink(chroot_path)
