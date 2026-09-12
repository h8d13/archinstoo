import os
from pathlib import Path
from typing import TYPE_CHECKING, Self

from archinstoo.lib import chroot, sysconfig, systemd
from archinstoo.lib.authentication import accounts
from archinstoo.lib.bootloader.install import BootloaderInstaller
from archinstoo.lib.disk import snapshots
from archinstoo.lib.disk.cleanup import teardown_layout
from archinstoo.lib.disk.cryptenroll import enroll_fido2, enroll_tpm2
from archinstoo.lib.disk.device_handler import DeviceHandler
from archinstoo.lib.disk.fstab import write_fstab
from archinstoo.lib.disk.keyfiles import KeyFileGenerator
from archinstoo.lib.disk.mount import LayoutMounter
from archinstoo.lib.exceptions import DiskError, HardwareIncompatibilityError, SysCallError
from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.kernel.initramfs import Initramfs
from archinstoo.lib.kernel.swap import setup_swapfile
from archinstoo.lib.kernel.sysctl import write_sysctl
from archinstoo.lib.kernel.zram import setup_zram
from archinstoo.lib.localization import configure
from archinstoo.lib.models.authentication import PrivilegeEscalation
from archinstoo.lib.models.bootloader import Bootloader
from archinstoo.lib.models.device import (
	DiskEncryption,
	DiskLayoutConfiguration,
	EncryptionType,
	FilesystemType,
	SnapshotType,
)
from archinstoo.lib.models.firmware import FirmwareConfiguration
from archinstoo.lib.models.kernel import DEFAULT_KERNEL
from archinstoo.lib.output import ARTIFACTS_STORE, debug, error, info, log, logger, warn
from archinstoo.lib.pm import Pacman, mirrors
from archinstoo.lib.pm.config import PacmanConfig

if TYPE_CHECKING:
	from subprocess import CompletedProcess
	from types import TracebackType

	from archinstoo.lib.args import ArchConfigHandler
	from archinstoo.lib.general import SysCommand
	from archinstoo.lib.models.locale import LocaleConfiguration
	from archinstoo.lib.models.mirrors import PacmanConfiguration
	from archinstoo.lib.models.packages import Repository
	from archinstoo.lib.models.service import UserService
	from archinstoo.lib.models.swap import SwapConfiguration
	from archinstoo.lib.models.users import User

# Base packages installed by default (firmware added based on FirmwareConfiguration)
# mkinitcpio is listed explicitly so pacstrap installs it deterministically. Otherwise
# pacman picks the first initramfs provider from the host's pacman.conf, which on non-Arch
# hosts (EndeavourOS prefers dracut, etc.) breaks the initramfs build and the
# UKI presets, both of which assume mkinitcpio is present in the chroot.
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
		# orders the steps the scripts call; each step is a thin entry into the
		# package named for its area
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
		if systemd.accessibility_tools_in_use():
			self._base_packages.extend(__accessibility_packages__)

		self.initramfs = Initramfs()
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
		systemd.wait_iso_services(self._args.skip_ntp, self._args.skip_wkd)

	def mount_ordered_layout(self) -> None:
		info(f'Mounting ordered layout at {self.target} (encryption: {self._disk_encryption.encryption_type.value})', step=True)
		self._layout_teardown_required = True
		self._fstab_entries.extend(LayoutMounter(self.target, self._disk_config, self._disk_encryption).mount())

	def generate_key_files(self) -> None:
		info(f'Generating key files for {self._disk_encryption.encryption_type.value}...')
		self.initramfs.files.extend(KeyFileGenerator(self.target, self._disk_encryption).generate())

	def post_install_check(self) -> list[str]:
		return [step for step, flag in self._helper_flags.items() if flag is False]

	def set_mirrors(self, pacman_configuration: PacmanConfiguration, on_target: bool = False) -> None:
		mirrors.set_mirrors(self, pacman_configuration, on_target)

	def genfstab(self, flags: str = '-pU') -> None:
		write_fstab(self.target, self._fstab_entries, flags)

	def set_hostname(self, hostname: str) -> None:
		sysconfig.write_hostname(self.target, hostname)

	def set_timezone(self, zone: str) -> bool:
		return configure.set_timezone(self, zone)

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
		systemd.enable_service(self, services)

	def disable_service(self, services: str | list[str]) -> None:
		systemd.disable_service(self, services)

	def enable_services_from_config(self, services: list[str | UserService]) -> None:
		systemd.enable_services_from_config(self, services)

	def arch_chroot(
		self,
		cmd: str | list[str],
		run_as: str | None = None,
		peek_output: bool = False,
		env: dict[str, str] | None = None,
	) -> SysCommand | CompletedProcess[bytes]:
		return chroot.arch_chroot(self.target, cmd, run_as, peek_output, env)

	def mkinitcpio(self, flags: list[str]) -> bool:
		return self.initramfs.build(self, flags)

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
			if 'bcachefs' not in self.initramfs.modules:
				debug('Adding bcachefs module to initramfs')
				self.initramfs.modules.append('bcachefs')
			if 'bcachefs' not in self.initramfs.hooks and 'block' in self.initramfs.hooks:
				debug('Inserting bcachefs hook after block')
				self.initramfs.hooks.insert(self.initramfs.hooks.index('block') + 1, 'bcachefs')

		# There is not yet an fsck tool for NTFS. If it's being used for the root filesystem, the hook should be removed.
		if fs_type.fs_type_mount == 'ntfs3' and mountpoint == self.target and 'fsck' in self.initramfs.hooks:
			debug('Removing fsck hook: no fsck tool for ntfs3 root')
			self.initramfs.hooks.remove('fsck')

	def _prepare_encrypt(self, before: str = 'filesystems') -> None:
		if 'sd-encrypt' not in self.initramfs.hooks:
			debug(f'Inserting sd-encrypt hook before {before}')
			self.initramfs.hooks.insert(self.initramfs.hooks.index(before), 'sd-encrypt')

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
			self.initramfs.hooks.insert(self.initramfs.hooks.index('filesystems') - 1, LVM)

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

		if ucode := SysInfo.ucode():
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

	def setup_btrfs_snapshot(self, snapshot_type: SnapshotType, bootloader: Bootloader | None = None) -> None:
		snapshots.setup_btrfs_snapshot(self, snapshot_type, bootloader)

	def setup_swap(self, config: SwapConfiguration) -> None:
		if config.zram:
			setup_zram(self, config.algorithm, config.recomp_algorithm)
			self._zram_enabled = True
		if config.hibernation:
			try:
				fstab_entry, kernel_params = setup_swapfile(self, config.size_gib)
			except (SysCallError, DiskError) as err:
				# hibernation is an enhancement, not worth aborting a
				# finished-installing system over (cf. allow_ssh)
				warn(f'Failed to set up hibernation swap file: {err}')
			else:
				self._fstab_entries.append(fstab_entry)
				self._kernel_params.extend(kernel_params)

	def setup_sysctl(self, entries: list[str]) -> None:
		write_sysctl(self.target, entries)

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
		keep_standalone = uki_enabled and bootloader == Bootloader.Grub and self._disk_config.btrfs_snapshot_type() is not None

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

	def create_users(
		self,
		users: User | list[User],
		privilege_escalation: PrivilegeEscalation | None = PrivilegeEscalation.Sudo,
	) -> None:
		accounts.create_users(self, users, privilege_escalation)

	def add_to_seat_group(self, usernames: list[str]) -> None:
		accounts.add_to_seat_group(self, usernames)

	def set_user_password(self, user: User) -> bool:
		return accounts.set_user_password(self, user)

	def lock_root_account(self) -> bool:
		return accounts.lock_root_account(self)

	def chown_tree(self, username: str, path: str) -> None:
		chroot.chown_tree(self, username, path)

	def set_locale(self, locale_config: LocaleConfiguration) -> bool:
		return configure.set_locale(self, locale_config)

	def set_vconsole(self, locale_config: LocaleConfiguration) -> None:
		configure.set_vconsole(self, locale_config)

	def set_keyboard(self, locale_config: LocaleConfiguration) -> bool:
		return configure.set_keyboard(self, locale_config)

	def set_environment(self, env_vars: dict[str, str]) -> None:
		sysconfig.write_environment(self.target, env_vars)
