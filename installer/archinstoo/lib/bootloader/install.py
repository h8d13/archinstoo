import re
import shlex
import shutil
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.disk.lvm import lvm_pvseg_info
from archinstoo.lib.disk.utils import get_lsblk_info, get_parent_device_path
from archinstoo.lib.exceptions import DiskError, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.linux_path import LPath
from archinstoo.lib.models.bootloader import Bootloader
from archinstoo.lib.models.device import (
	DiskEncryption,
	EncryptionType,
	LvmVolume,
	PartitionModification,
	SnapshotType,
	has_separate_boot,
)
from archinstoo.lib.output import debug, error, info, warn

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


def configure_grub_btrfsd(target: Path, snapshot_type: SnapshotType) -> None:
	if snapshot_type == SnapshotType.Timeshift:
		snapshot_path = '--timeshift-auto'
	elif snapshot_type == SnapshotType.Snapper:
		snapshot_path = '/.snapshots'
	else:
		raise ValueError('Unsupported snapshot type')

	debug(f'Configuring grub-btrfsd service for {snapshot_type} at {snapshot_path}')

	# Works for either snapper or ts just adapting default paths above
	# https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html#id-1.14.3
	systemd_dir = target / 'etc/systemd/system/grub-btrfsd.service.d'
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


def _luks_uuid_from_mapper_dev(mapper_dev_path: Path) -> str:
	# rd.luks.name= wants the container UUID, lsblk reversed from the mapper
	# device lands on it as the first parent
	lsblk_info = get_lsblk_info(mapper_dev_path, reverse=True, full_dev_path=True)

	if not lsblk_info.children or not lsblk_info.children[0].uuid:
		raise ValueError('Unable to determine UUID of luks superblock')

	return lsblk_info.children[0].uuid


def refind_kernel_dir(root: PartitionModification | LvmVolume, *, boot_on_root: bool) -> str:
	# Directory holding vmlinuz/initramfs in refind's backslash form,
	# relative to the volume refind addresses. On a btrfs root nothing
	# sets a default subvolume, so the root subvolume is part of the path.
	if not boot_on_root:
		# kernels sit at the top of the ESP or a separate /boot partition
		return '\\'
	subvols = root.btrfs_subvols
	if subvols:
		root_subvol = next((sv for sv in subvols if sv.is_root()), None)
		if root_subvol:
			return f'{root_subvol.name}\\boot\\'
	return '\\boot\\'


class BootloaderInstaller:
	# One per add_bootloader() call. Runs on the mounted target through the
	# Installer (chroot, pacstrap, mkinitcpio); what it needs from the install
	# state is fixed by the time the bootloader goes in, so it is handed over
	# once instead of read back through private attributes.
	def __init__(
		self,
		installation: Installer,
		disk_encryption: DiskEncryption,
		kernel_params: list[str],
		zram_enabled: bool,
	) -> None:
		self._inst = installation
		self.target = installation.target
		self.kernels = installation.kernels
		self.pacman = installation.pacman
		self._enc = disk_encryption
		# extra cmdline entries collected during the install (resume=, quiet, console=)
		self._extra_params = kernel_params
		self._zram = zram_enabled

	def install(
		self,
		bootloader: Bootloader,
		boot_partition: PartitionModification,
		efi_partition: PartitionModification | None,
		root: PartitionModification | LvmVolume,
		*,
		uki_enabled: bool = False,
		removable: bool = False,
		splash: bool = False,
		keep_standalone_initramfs: bool = False,
	) -> None:
		if uki_enabled:
			self._config_uki(root, efi_partition, keep_standalone_initramfs=keep_standalone_initramfs, splash=splash)

		match bootloader:
			case Bootloader.Systemd:
				self._add_systemd_bootloader(boot_partition, root, efi_partition, uki_enabled)
			case Bootloader.Grub:
				self._add_grub_bootloader(boot_partition, root, efi_partition, uki_enabled, removable)
			case Bootloader.Efistub:
				self._add_efistub_bootloader(boot_partition, root, uki_enabled)
			case Bootloader.Limine:
				self._add_limine_bootloader(boot_partition, efi_partition, root, uki_enabled, removable)
			case Bootloader.Refind:
				self._add_refind_bootloader(boot_partition, efi_partition, root, uki_enabled)

		# Seed /loader/random-seed in the chroot so the very first boot isn't
		# entropy-starved. Consumed by systemd-boot, or for a UKI by the embedded
		# systemd-stub regardless of which bootloader chainloads it. The EFI system
		# token can't be written here (no NVRAM in the chroot);
		# systemd-boot-random-seed.service sets it on the first real boot.
		if efi_partition is not None and (uki_enabled or bootloader == Bootloader.Systemd):
			seed_cmd = ['bootctl', '--graceful']
			if has_separate_boot(boot_partition, efi_partition):
				seed_cmd.append(f'--esp-path={efi_partition.mountpoint}')
			seed_cmd.append('random-seed')
			try:
				self._inst.arch_chroot(seed_cmd)
			except SysCallError as err:
				# non-fatal: stub falls back to firmware RNG, service reseeds on boot
				warn(f'Could not seed bootloader random seed: {err}')

	def _get_kernel_params_partition(
		self,
		root_partition: PartitionModification,
		id_root: bool = True,
		partuuid: bool = True,
	) -> list[str]:
		kernel_parameters = []

		if root_partition in self._enc.partitions:
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

		match self._enc.encryption_type:
			case EncryptionType.LVM_ON_LUKS:
				if not lvm.vg_name:
					raise ValueError(f'Unable to determine VG name for {lvm.name}')

				pv_seg_info = lvm_pvseg_info(lvm.vg_name, lvm.name)

				if not pv_seg_info:
					raise ValueError(f'Unable to determine PV segment info for {lvm.vg_name}/{lvm.name}')

				uuid = _luks_uuid_from_mapper_dev(pv_seg_info.pv_name)

				debug(f'LvmOnLuks, encrypted root partition, identifying by UUID: {uuid}')
				kernel_parameters.append(f'rd.luks.name={uuid}=cryptlvm root={lvm.safe_dev_path}')
			case EncryptionType.LUKS_ON_LVM:
				uuid = _luks_uuid_from_mapper_dev(lvm.mapper_path)

				debug(f'LuksOnLvm, encrypted root partition, identifying by UUID: {uuid}')
				kernel_parameters.append(f'rd.luks.name={uuid}=root root=/dev/mapper/root')
			case EncryptionType.NO_ENCRYPTION:
				debug(f'Identifying root lvm by mapper device: {lvm.dev_path}')
				kernel_parameters.append(f'root={lvm.safe_dev_path}')
			case EncryptionType.LUKS:
				pass

		return kernel_parameters

	def _get_kernel_params(
		self,
		root: PartitionModification | LvmVolume,
		id_root: bool = True,
		partuuid: bool = True,
	) -> list[str]:
		kernel_parameters = (
			self._get_kernel_params_lvm(root) if isinstance(root, LvmVolume) else self._get_kernel_params_partition(root, id_root, partuuid)
		)

		# Zswap should be disabled when using zram.
		# https://github.com/archlinux/archinstall/issues/881
		if self._zram:
			kernel_parameters.append('zswap.enabled=0')

		if self._enc.encryption_type != EncryptionType.NO_ENCRYPTION:
			# All options must be joined into a single rd.luks.options=: systemd's
			# cryptsetup-generator does not merge repeated non-UUID occurrences, the
			# last one wins, so separate tpm2/fido2 params would silently drop one.
			luks_options = []
			if self._enc.tpm2_unlock:
				luks_options.append('tpm2-device=auto')
			if self._enc.fido2_device:
				# auto, not the enrolled hidraw path: hidraw numbering is not stable across boots.
				# password-echo=no per upstream archlinux/archinstall#1196
				# token-timeout: absent token otherwise holds the PIN/token prompt
				# for the 30s default before falling back to the passphrase query
				luks_options.append('fido2-device=auto,token-timeout=5,password-echo=no')
			if luks_options:
				kernel_parameters.append('rd.luks.options=' + ','.join(luks_options))

		if id_root:
			for sub_vol in root.btrfs_subvols:
				if sub_vol.is_root():
					kernel_parameters.append(f'rootflags=subvol={sub_vol.name}')
					break

			kernel_parameters.append('rw')

		kernel_parameters.append(f'rootfstype={root.safe_fs_type.fs_type_mount}')
		kernel_parameters.extend(self._extra_params)

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
			debug(f'Wrote {entry_conf}')

	def _add_systemd_bootloader(
		self,
		boot_partition: PartitionModification,
		root: PartitionModification | LvmVolume,
		efi_partition: PartitionModification | None,
		uki_enabled: bool = False,
	) -> None:
		debug('Installing systemd bootloader')

		self.pacman.strap(Bootloader.Systemd.packages())

		if not efi_partition:
			raise ValueError('Could not detect EFI system partition')
		if not efi_partition.mountpoint:
			raise ValueError('EFI system partition is not mounted')

		bootctl_options = []

		# A UKI is self-contained on the ESP (EFI/Linux), so systemd-boot reads
		# nothing from a separate boot partition even though pacman still drops
		# the raw kernel there. Naming it makes bootctl demand XBOOTLDR typing
		# for no gain, and plain BOOT-flagged /boot then fails the install.
		if not uki_enabled and has_separate_boot(boot_partition, efi_partition):
			bootctl_options.append(f'--esp-path={efi_partition.mountpoint}')
			bootctl_options.append(f'--boot-path={boot_partition.mountpoint}')

		# bootctl since v257 detects arch-chroot as a container and silently
		# skips writing EFI boot variables; --variables=BOOL (systemd >=258)
		# forces the choice. We always pacstrap a current Arch target, so the
		# flag is always present. https://github.com/systemd/systemd/pull/37144
		def _bootctl_install(variables: str) -> None:
			argv = ' '.join(('bootctl', variables, *bootctl_options, 'install'))
			self._inst.arch_chroot(argv)

		try:
			_bootctl_install('--variables=yes')
		except SysCallError as err:
			# retry leaving the EFI variables untouched (e.g. vars not writable)
			warn(f'bootctl could not write EFI variables ({err}), retrying with --variables=no')
			_bootctl_install('--variables=no')

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
		debug(f'Wrote {loader_conf}')

	def _add_grub_bootloader(
		self,
		boot_partition: PartitionModification,
		root: PartitionModification | LvmVolume,
		efi_partition: PartitionModification | None,
		uki_enabled: bool = False,
		removable: bool = False,
	) -> None:
		debug('Installing grub bootloader')

		self.pacman.strap(Bootloader.Grub.packages(SysInfo.has_uefi()))

		# enable GRUB cryptodisk before grub-install so crypto modules
		# are embedded in the core image (required for encrypted /boot)
		grub_default = self.target / 'etc/default/grub'
		if self._enc.encryption_type != EncryptionType.NO_ENCRYPTION:
			config = grub_default.read_text()
			config = re.sub(r'^#(GRUB_ENABLE_CRYPTODISK=y)', r'\1', config, flags=re.MULTILINE)
			grub_default.write_text(config)

		info(f'GRUB boot partition: {boot_partition.dev_path}')

		command = [
			*self._inst.arch_chroot_prefix,
			'grub-install',
			'--debug',
		]

		if SysInfo.has_uefi():
			if not efi_partition:
				raise ValueError('Could not detect efi partition')

			info(f'GRUB EFI partition: {efi_partition.dev_path}')

			if SysInfo.arch() == 'aarch64':
				# grub names its EFI target arm64, not aarch64
				grub_target = 'arm64-efi'
			elif SysInfo.bitness() == 64:
				grub_target = 'x86_64-efi'
			else:
				# https://wiki.archlinux.org/title/Unified_Extensible_Firmware_Interface
				# mixed mode boot handling same as limine handling 32bit UEFI on 64-bit CPUs
				grub_target = 'i386-efi'

			add_options = [
				f'--target={grub_target}',
				f'--efi-directory={efi_partition.mountpoint}',
				'--bootloader-id=GRUB',
			]

			if removable:
				add_options.append('--removable')

			command.extend(add_options)

			try:
				SysCommand(command, peek_output=True, silent=True)
			except SysCallError as err:
				if removable or 'efibootmgr' not in str(err):
					raise DiskError(f'Could not install GRUB to {self.target}{efi_partition.mountpoint}: {err}') from err
				# firmware refused the NVRAM entry (full, read-only): EFI/BOOT needs none
				# https://github.com/archlinux/archinstall/issues/3976
				warn(f'grub-install could not register a boot entry, installing as removable instead: {err}')
				try:
					SysCommand([*command, '--removable'], peek_output=True, silent=True)
				except SysCallError as err2:
					raise DiskError(f'Could not install GRUB to {self.target}{efi_partition.mountpoint}: {err2}') from err2
		else:
			info(f'GRUB boot partition: {boot_partition.dev_path}')

			parent_dev_path = get_parent_device_path(boot_partition.safe_dev_path)

			add_options = [
				'--target=i386-pc',
				'--recheck',
				str(parent_dev_path),
			]

			try:
				SysCommand(command + add_options, peek_output=True, silent=True)
			except SysCallError as err:
				raise DiskError(f'Failed to install GRUB boot on {boot_partition.dev_path}: {err}') from err

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
				debug('Enabled 15_uki and disabled 10_linux in /etc/grub.d')
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
			self._inst.arch_chroot(
				'grub-mkconfig -o /boot/grub/grub.cfg',
			)
		except SysCallError as err:
			raise DiskError(f'Could not configure GRUB: {err}') from err

	def _add_limine_bootloader(
		self,
		boot_partition: PartitionModification,
		efi_partition: PartitionModification | None,
		root: PartitionModification | LvmVolume,
		uki_enabled: bool = False,
		removable: bool = False,
	) -> None:
		debug('Installing Limine bootloader')

		self.pacman.strap(Bootloader.Limine.packages(SysInfo.has_uefi()))

		info(f'Limine boot partition: {boot_partition.dev_path}')

		limine_path = self.target / 'usr' / 'share' / 'limine'
		config_path = None
		hook_command = None

		if SysInfo.has_uefi():
			if not efi_partition:
				raise ValueError('Could not detect efi partition')
			if not efi_partition.mountpoint:
				raise ValueError('EFI partition is not mounted')

			info(f'Limine EFI partition: {efi_partition.dev_path}')

			parent_dev_path = get_parent_device_path(efi_partition.safe_dev_path)

			# limine ships arch-specific default EFI binaries; 64-bit one last
			efi_binaries: tuple[str, ...] = ('BOOTAA64.EFI',) if SysInfo.arch() == 'aarch64' else ('BOOTIA32.EFI', 'BOOTX64.EFI')

			try:
				efi_dir_path = self.target / efi_partition.mountpoint.relative_to('/') / 'EFI'
				efi_dir_path_target = efi_partition.mountpoint / 'EFI'
				subdir = 'BOOT' if removable else 'arch-limine'
				efi_dir_path = efi_dir_path / subdir
				efi_dir_path_target = efi_dir_path_target / subdir
				config_path = efi_dir_path / 'limine.conf'

				efi_dir_path.mkdir(parents=True, exist_ok=True)

				for file in efi_binaries:
					(limine_path / file).copy_into(efi_dir_path)
			except Exception as err:
				raise DiskError(f'Failed to install Limine in {self.target}{efi_partition.mountpoint}: {err}') from err

			hook_command = ' && '.join(f'/usr/bin/cp /usr/share/limine/{file} {efi_dir_path_target}/' for file in efi_binaries)

			if not removable:
				# Create EFI boot menu entry for Limine.
				try:
					# see https://wiki.archlinux.org/title/Arch_boot_process
					# mixed mode booting (32bit UEFI on x86_64 CPU)
					efi_bitness = SysInfo.bitness()
				except Exception as err:
					raise OSError(f'Could not open or read /sys/ to determine EFI bitness: {err}') from err

				if efi_bitness == 64:
					loader_path = f'\\EFI\\arch-limine\\{efi_binaries[-1]}'
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
				except SysCallError as err:
					# same firmware failure as grub: EFI/BOOT/BOOT*.EFI boots without an entry
					# https://github.com/archlinux/archinstall/issues/3990
					warn(f'efibootmgr could not register Limine, installing as removable instead: {err}')
					self._add_limine_bootloader(boot_partition, efi_partition, root, uki_enabled, removable=True)
					return
		else:
			boot_limine_path = self.target / 'boot' / 'limine'
			boot_limine_path.mkdir(parents=True, exist_ok=True)

			config_path = boot_limine_path / 'limine.conf'

			parent_dev_path = get_parent_device_path(boot_partition.safe_dev_path)

			if unique_path := self._inst.device_handler.get_unique_path_for_device(parent_dev_path):
				parent_dev_path = unique_path

			try:
				# The `limine-bios.sys` file contains stage 3 code.
				(limine_path / 'limine-bios.sys').copy_into(boot_limine_path)

				# `limine bios-install` deploys the stage 1 and 2 to the
				self._inst.arch_chroot(f'limine bios-install {parent_dev_path}', peek_output=True)
			except Exception as err:
				raise DiskError(f'Failed to install Limine on {parent_dev_path}: {err}') from err

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
		debug(f'Wrote pacman hook {hook_path}')

		path_root = 'boot()'
		if efi_partition:
			if has_separate_boot(boot_partition, efi_partition):
				path_root = f'uuid({boot_partition.partuuid})'
			elif efi_partition.mountpoint != Path('/boot') and isinstance(root, PartitionModification):
				path_root = f'uuid({root.partuuid})'

		self._install_limine_entries_hook(config_path, path_root, self._get_kernel_params(root), uki_enabled)

	def _install_limine_entries_hook(self, config_path: Path, path_root: str, kernel_params: list[str], uki: bool) -> None:
		# limine.conf is a static list and limine has no EFI/Linux discovery: the
		# target regenerates it from /usr/lib/modules/*/pkgbase, at install and on
		# every kernel install/remove (after 90-mkinitcpio-install built the image)
		if uki:
			entry = ['protocol: efi', 'path: boot():/EFI/Linux/arch-$k.efi', 'cmdline: $cmdline']
		else:
			entry = ['protocol: linux', f'path: {path_root}:/vmlinuz-$k', 'cmdline: $cmdline', f'module_path: {path_root}:/initramfs-$k.img']
		conf = Path('/') / config_path.relative_to(self.target)
		# entry lines substituted after dedent: they carry their own indent
		entries = '\n'.join(f'\t\tprintf \'    %s\\n\' "{it}"' for it in entry)
		script = textwrap.dedent(
			f"""\
			#!/bin/sh
			# archinstoo: limine kernel entries, regenerated on kernel changes (hand edits do not survive)
			set -e
			conf={shlex.quote(str(conf))}
			cmdline={shlex.quote(' '.join(kernel_params))}
			{{
				printf 'timeout: 5\\n'
				# name order, not module-dir (version) order: plain linux stays the default entry
				for k in $(cat /usr/lib/modules/*/pkgbase | sort -u); do
					printf '\\n/Arch Linux (%s)\\n' "$k"
			@ENTRIES@
				done
			}} > "$conf"
			"""
		).replace('@ENTRIES@', entries)
		script_path = self.target / 'etc/archinstoo.d/limine-entries.sh'
		script_path.parent.mkdir(parents=True, exist_ok=True)
		script_path.write_text(script)
		script_path.chmod(0o755)

		hook = textwrap.dedent(
			"""\
			[Trigger]
			Type = Path
			Operation = Install
			Operation = Upgrade
			Operation = Remove
			Target = usr/lib/modules/*/pkgbase

			[Action]
			Description = Updating Limine kernel entries...
			When = PostTransaction
			Exec = /etc/archinstoo.d/limine-entries.sh
			"""
		)
		hooks_dir = self.target / 'etc/pacman.d/hooks'
		hooks_dir.mkdir(parents=True, exist_ok=True)
		(hooks_dir / '91-limine-entries.hook').write_text(hook)

		self._inst.arch_chroot('/etc/archinstoo.d/limine-entries.sh')
		debug(f'Wrote {config_path} via limine-entries.sh')

	def _add_efistub_bootloader(
		self,
		boot_partition: PartitionModification,
		root: PartitionModification | LvmVolume,
		uki_enabled: bool = False,
	) -> None:
		debug('Installing efistub bootloader')

		self.pacman.strap(Bootloader.Efistub.packages())

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
			info(f'Creating EFI boot entry for {kernel}')
			cmd = [arg.format(kernel=kernel) for arg in cmd_template]
			try:
				SysCommand(cmd)
			except SysCallError as err:
				if not uki_enabled:
					raise DiskError(f'efibootmgr could not register {kernel} and a plain kernel has no removable fallback: {err}') from err
				esp = self.target / boot_partition.relative_mountpoint
				fallback = esp / 'EFI/BOOT' / ('BOOTAA64.EFI' if SysInfo.arch() == 'aarch64' else 'BOOTX64.EFI')
				fallback.parent.mkdir(parents=True, exist_ok=True)
				shutil.copy2(esp / 'EFI/Linux' / f'arch-{kernel}.efi', fallback)
				warn(f'efibootmgr could not register {kernel}, copied its UKI to {fallback.relative_to(self.target)} instead: {err}')
				break

	def _add_refind_bootloader(
		self,
		boot_partition: PartitionModification,
		efi_partition: PartitionModification | None,
		root: PartitionModification | LvmVolume,
		uki_enabled: bool = False,
	) -> None:
		debug('Installing rEFInd bootloader')

		self.pacman.strap(Bootloader.Refind.packages())

		info(f'rEFInd boot partition: {boot_partition.dev_path}')

		if not efi_partition:
			raise ValueError('Could not detect EFI system partition')
		if not efi_partition.mountpoint:
			raise ValueError('EFI system partition is not mounted')

		info(f'rEFInd EFI partition: {efi_partition.dev_path}')

		try:
			self._inst.arch_chroot('refind-install')
		except SysCallError as err:
			raise DiskError(f'Could not install rEFInd to {self.target}{efi_partition.mountpoint}: {err}') from err

		if not boot_partition.mountpoint:
			raise ValueError('Boot partition is not mounted, cannot write rEFInd config')

		if has_separate_boot(boot_partition, efi_partition):
			# kernels sit on their own /boot partition
			config_path = self.target / boot_partition.mountpoint.relative_to('/') / 'refind_linux.conf'
			boot_on_root = False
		else:
			# ESP at /boot means the kernels are on it; anywhere else
			# (/efi, /boot/efi, ...) leaves them on root's /boot
			config_path = self.target / 'boot' / 'refind_linux.conf'
			boot_on_root = efi_partition.mountpoint != Path('/boot')

		config_contents = []

		kernel_params = ' '.join(self._get_kernel_params(root))

		for kernel in self.kernels:
			if uki_enabled:
				entry = f'"Arch Linux ({kernel}) UKI" "{kernel_params}"'
			else:
				kernel_dir = refind_kernel_dir(root, boot_on_root=boot_on_root)
				initrd_path = f'initrd={kernel_dir}initramfs-{kernel}.img'
				entry = f'"Arch Linux ({kernel})" "{kernel_params} {initrd_path}"'

			config_contents.append(entry)

		config_path.write_text('\n'.join(config_contents) + '\n')
		debug(f'Wrote {config_path}')

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
		debug(f'Wrote pacman hook {hook_path}')

	def _config_uki(
		self,
		root: PartitionModification | LvmVolume,
		efi_partition: PartitionModification | None,
		keep_standalone_initramfs: bool = False,
		splash: bool = False,
	) -> None:
		info('Configuring UKI images...', step=True)

		if not efi_partition or not efi_partition.mountpoint:
			raise ValueError(f'Could not detect ESP at mountpoint {self.target}')

		# Set up kernel command line
		cmdline_path = self.target / 'etc/kernel/cmdline'
		with cmdline_path.open('w') as cmdline:
			kernel_parameters = self._get_kernel_params(root)
			cmdline.write(' '.join(kernel_parameters) + '\n')
		debug(f'Wrote {cmdline_path}')

		diff_mountpoint = None

		if efi_partition.mountpoint != Path('/efi'):
			diff_mountpoint = str(efi_partition.mountpoint)

		# default_* only: PRESETS stays ('default'), the fallback lines are left as shipped
		image_re = re.compile(r'(default_image="/([^"]+).+\n)')
		uki_re = re.compile(r'#((default_uki=")/[^/]+(.+\n))')
		presets_re = re.compile(r'^(PRESETS=)\((.*)\)\s*$')

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
			debug(f'Wrote {osrelease_dir / kernel}')

			preset = self.target / 'etc/mkinitcpio.d' / (kernel + '.preset')
			config = preset.read_text().splitlines(True)

			for index, line in enumerate(config):
				# Avoid storing redundant image file (unless grub-btrfs needs it for snapshot entries)
				if m := image_re.match(line):
					if keep_standalone_initramfs:
						continue
					image = self.target / m.group(2)
					image.unlink(missing_ok=True)
					debug(f'Removed standalone initramfs {image}')
					config[index] = '#' + m.group(1)
				elif m := uki_re.match(line):
					if diff_mountpoint:
						config[index] = m.group(2) + diff_mountpoint + m.group(3)
					else:
						config[index] = m.group(1)
				elif line.startswith('#default_options='):
					# rebuild deterministically: the mkinitcpio template ships
					# default_options with --splash, which we drop unless asked.
					opts = f'--osrelease /etc/os-release.d/{kernel}'
					if splash:
						opts += ' --splash /usr/share/systemd/bootctl/splash-arch.bmp'
					config[index] = f'default_options="{opts}"\n'
				elif keep_standalone_initramfs and (pm := presets_re.match(line)):
					tokens = [t.strip().strip('\'"') for t in pm.group(2).split(',') if t.strip()]
					if 'default' not in tokens:
						tokens.insert(0, 'default')
					config[index] = f'{pm.group(1)}({" ".join(repr(t) for t in tokens)})\n'

			preset.write_text(''.join(config))
			debug(f'Updated preset {preset}')

		self._install_uki_preset_hook(diff_mountpoint or '/efi', keep_standalone_initramfs, splash)

		# Directory for the UKIs
		uki_dir = self.target / efi_partition.relative_mountpoint / 'EFI/Linux'
		uki_dir.mkdir(parents=True, exist_ok=True)

		# Build the UKIs
		if not self._inst.mkinitcpio(['-P']):
			error('Error generating initramfs (continuing anyway)')

	def _install_uki_preset_hook(self, esp: str, keep_standalone_initramfs: bool, splash: bool) -> None:
		# kernels installed later get mkinitcpio's stock preset (plain initramfs), so no UKI
		# and no boot entry. Runs before 90-mkinitcpio-install, which keeps an existing preset.
		# https://github.com/archlinux/archinstall/issues/4680
		options = '--osrelease /etc/os-release.d/$pkgbase'
		if splash:
			options += ' --splash /usr/share/systemd/bootctl/splash-arch.bmp'
		seds = [
			'"s|%PKGBASE%|$pkgbase|g"',
			f'"s|^#default_uki=\\"/efi|default_uki=\\"{esp}|"',
			f'"s|^#default_options=.*|default_options=\\"{options}\\"|"',
		]
		if not keep_standalone_initramfs:
			seds.append('"s|^default_image=|#default_image=|"')
		sed_args = ' '.join(f'-e {e}' for e in seds)
		script = textwrap.dedent(
			f"""\
			#!/bin/sh
			# archinstoo: UKI preset + os-release for kernels installed after the fact
			set -e
			while read -r pkgbase_path; do
				pkgbase=$(cat "/$pkgbase_path")
				preset="/etc/mkinitcpio.d/$pkgbase.preset"
				[ -e "$preset" ] && continue
				mkdir -p /etc/os-release.d
				osrel="/etc/os-release.d/$pkgbase"
				[ -e "$osrel" ] || sed "s/^PRETTY_NAME=.*/PRETTY_NAME=\\"Arch Linux ($pkgbase)\\"/" /etc/os-release > "$osrel"
				sed {sed_args} /usr/share/mkinitcpio/hook.preset > "$preset"
			done
			"""
		)
		script_path = self.target / 'etc/archinstoo.d/uki-preset.sh'
		script_path.parent.mkdir(parents=True, exist_ok=True)
		script_path.write_text(script)
		script_path.chmod(0o755)

		hook = textwrap.dedent(
			"""\
			[Trigger]
			Type = Path
			Operation = Install
			Target = usr/lib/modules/*/pkgbase

			[Action]
			Description = Creating UKI preset for new kernel...
			When = PostTransaction
			Exec = /etc/archinstoo.d/uki-preset.sh
			NeedsTargets
			"""
		)
		hooks_dir = self.target / 'etc/pacman.d/hooks'
		hooks_dir.mkdir(parents=True, exist_ok=True)
		(hooks_dir / '89-uki-preset.hook').write_text(hook)
		debug(f'Wrote {script_path} and pacman hook 89-uki-preset.hook')
