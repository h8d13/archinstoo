import json
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.disk.lvm import lvm_pvseg_info
from archinstoo.lib.disk.mdadm import array_uuid
from archinstoo.lib.disk.utils import get_lsblk_info, get_parent_device_path
from archinstoo.lib.exceptions import DiskError, HardwareIncompatibilityError, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.models.bootloader import GRUB_ESP, Bootloader
from archinstoo.lib.models.device import (
	DiskEncryption,
	EncryptionType,
	LvmVolume,
	PartitionModification,
	has_separate_boot,
)
from archinstoo.lib.output import debug, info, warn

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.device import DiskLayoutConfiguration

_GRUB_EFI_DIR = 'EFI/fedora'
# efistub's fixed UKI, under $BOOT (the ESP), and the plugin keeping it current
_EFISTUB_UKI = 'EFI/Linux/fedora.efi'
_EFISTUB_PLUGIN = '95-fedinstoo-efistub.install'


def _efi_fallback() -> str:
	# what firmware boots with no entry pointing anywhere
	return 'EFI/BOOT/BOOTAA64.EFI' if SysInfo.arch() == 'aarch64' else 'EFI/BOOT/BOOTX64.EFI'


def _luks_uuid_from_mapper_dev(mapper_dev_path: Path) -> str:
	# rd.luks.name= wants the container UUID, lsblk reversed from the mapper
	# device lands on it as the first parent
	lsblk_info = get_lsblk_info(mapper_dev_path, reverse=True, full_dev_path=True)

	if not lsblk_info.children or not lsblk_info.children[0].uuid:
		raise ValueError('Unable to determine UUID of luks superblock')

	return lsblk_info.children[0].uuid


class BootloaderInstaller:
	# One per add_bootloader() call. Resolves boot/ESP/root from the layout,
	# then: kernel cmdline + kernel-install layout, the loader itself, and the
	# kernels last. Their posttrans runs kernel-install, which writes the BLS
	# entries or UKIs where the loader just went, so nothing here names a
	# kernel file
	def __init__(
		self,
		installation: Installer,
		disk_config: DiskLayoutConfiguration,
		disk_encryption: DiskEncryption,
		kernel_params: list[str],
		zram_enabled: bool,
	) -> None:
		self._inst = installation
		self.target = installation.target
		self.dnf = installation.dnf
		self._disk_config = disk_config
		self._enc = disk_encryption
		# extra cmdline entries collected during the install (resume=), plus
		# quiet/console= added by install(); a copy, the install's list stays put
		self._extra_params = list(kernel_params)
		self._zram = zram_enabled

	def _partitions(self) -> tuple[PartitionModification, PartitionModification | None, PartitionModification | LvmVolume]:
		efi_partition = self._disk_config.get_efi_partition()
		boot_partition = self._disk_config.get_boot_partition()
		root = self._disk_config.get_root()

		# nothing at /boot: the ESP carries the kernels, see has_separate_boot
		if boot_partition is None:
			if SysInfo.has_uefi() and efi_partition is not None:
				boot_partition = efi_partition
			else:
				raise ValueError(f'Could not detect boot at mountpoint {self.target}')

		if root is None:
			raise ValueError(f'Could not detect root at mountpoint {self.target}')

		return boot_partition, efi_partition, root

	def _add_param(self, param: str) -> None:
		if param not in self._extra_params:
			self._extra_params.append(param)

	def install(
		self,
		bootloader: Bootloader | None,
		*,
		uki_enabled: bool = False,
		removable: bool = False,
		quiet: bool = False,
		serial_console: str | None = None,
	) -> None:
		if quiet:
			self._add_param('quiet')
		if serial_console:
			self._add_param(f'console={serial_console}')

		root = self._disk_config.get_root()
		if root is None:
			raise ValueError(f'Could not detect root at mountpoint {self.target}')

		if bootloader is None:
			# --skip-boot: the kernels still go in, kernel-install picks its
			# own layout from whatever $BOOT it finds
			self._inst.install_kernels(self._get_kernel_params(root))
			return

		boot_partition, efi_partition, root = self._partitions()
		info(f'Adding bootloader {bootloader.display_name()} to {boot_partition.dev_path}', step=True)

		if not SysInfo.has_uefi() and not bootloader.has_bios_support():
			raise HardwareIncompatibilityError

		self._write_install_conf(bootloader, uki_enabled)

		match bootloader:
			case Bootloader.Systemd:
				self._add_systemd_bootloader(boot_partition, efi_partition, uki_enabled, removable)
				self._inst.install_kernels(self._get_kernel_params(root))
			case Bootloader.Grub:
				params = self._get_kernel_params(root)
				self._add_grub_bootloader(boot_partition, efi_partition, removable, params)
				self._inst.install_kernels(params)
				self._grub_mkconfig()
			case Bootloader.Efistub:
				self._add_efistub_bootloader(efi_partition, root, removable)

		# Seed /loader/random-seed so the very first boot isn't entropy-starved.
		# Consumed by systemd-boot, or for a UKI by the embedded systemd-stub.
		# systemd-boot-random-seed.service sets the EFI token on first boot
		if efi_partition is not None and bootloader != Bootloader.Grub:
			seed_cmd = ['bootctl', '--graceful']
			if has_separate_boot(boot_partition, efi_partition):
				seed_cmd.append(f'--esp-path={efi_partition.mountpoint}')
			seed_cmd.append('random-seed')
			try:
				self._inst.arch_chroot(seed_cmd)
			except SysCallError as err:
				# non-fatal: stub falls back to firmware RNG, service reseeds on boot
				warn(f'Could not seed bootloader random seed: {err}')

	def _write_install_conf(self, bootloader: Bootloader, uki_enabled: bool) -> None:
		# kernel-install's own choice of layout depends on what it finds on
		# $BOOT at the time; pin it so the result does not hinge on ordering.
		# GRUB is 'other': under 'bls' kernel-install creates $BOOT/<id>/<ver>
		# on the ESP, which 20-grub.install reads as another loader owning the
		# kernels and bows out, leaving /boot/loader/entries empty
		if uki_enabled:
			lines = ['layout=uki', 'uki_generator=ukify']
		elif bootloader == Bootloader.Grub:
			lines = ['layout=other']
		else:
			lines = ['layout=bls']
		lines.append('initrd_generator=dracut')
		conf = self.target / 'etc/kernel/install.conf'
		conf.parent.mkdir(parents=True, exist_ok=True)
		conf.write_text('\n'.join(lines) + '\n')
		debug(f'Wrote {conf}: {", ".join(lines)}')

	def _get_kernel_params_partition(self, root_partition: PartitionModification) -> list[str]:
		return [*self._md_params(root_partition), *self._root_params(root_partition)]

	def _md_params(self, root_partition: PartitionModification) -> list[str]:
		# dracut only assembles the arrays rd.md.uuid names; anaconda passes
		# the root's from blivet's dracut_setup_args() the same way
		# https://github.com/rhinstaller/anaconda/blob/d6be1da760e15bc3b95e0aecd9defef28b69f3ca/pyanaconda/modules/storage/bootloader/base.py#L860-L893
		if not root_partition.on_raid:
			return []
		return [f'rd.md.uuid={array_uuid(root_partition.safe_dev_path)}']

	def _root_params(self, root_partition: PartitionModification) -> list[str]:
		if root_partition in self._enc.partitions:
			debug(f'Root partition is an encrypted device, identifying by UUID: {root_partition.uuid}')
			return [f'rd.luks.name={root_partition.uuid}=root', 'root=/dev/mapper/root']

		if root_partition.partuuid:
			debug(f'Identifying root partition by PARTUUID: {root_partition.partuuid}')
			return [f'root=PARTUUID={root_partition.partuuid}']

		# an md array has no partition entry to take a PARTUUID from
		if root_partition.uuid:
			debug(f'No PARTUUID on {root_partition.dev_path}, identifying root by UUID: {root_partition.uuid}')
			return [f'root=UUID={root_partition.uuid}']

		raise ValueError(f'Could not identify root on {root_partition.dev_path}: no PARTUUID or UUID')

	def _get_kernel_params_lvm(self, lvm: LvmVolume) -> list[str]:
		match self._enc.encryption_type:
			case EncryptionType.LVM_ON_LUKS:
				if not lvm.vg_name:
					raise ValueError(f'Unable to determine VG name for {lvm.name}')

				pv_seg_info = lvm_pvseg_info(lvm.vg_name, lvm.name)
				if not pv_seg_info:
					raise ValueError(f'Unable to determine PV segment info for {lvm.vg_name}/{lvm.name}')

				uuid = _luks_uuid_from_mapper_dev(pv_seg_info.pv_name)
				debug(f'LvmOnLuks, encrypted root partition, identifying by UUID: {uuid}')
				return [f'rd.luks.name={uuid}=cryptlvm', f'root={lvm.safe_dev_path}']
			case EncryptionType.LUKS_ON_LVM:
				uuid = _luks_uuid_from_mapper_dev(lvm.mapper_path)
				debug(f'LuksOnLvm, encrypted root partition, identifying by UUID: {uuid}')
				return [f'rd.luks.name={uuid}=root', 'root=/dev/mapper/root']
			case EncryptionType.NO_ENCRYPTION:
				debug(f'Identifying root lvm by mapper device: {lvm.dev_path}')
				return [f'root={lvm.safe_dev_path}']
			case EncryptionType.LUKS:
				return []

	def _get_kernel_params(self, root: PartitionModification | LvmVolume) -> list[str]:
		kernel_parameters = self._get_kernel_params_lvm(root) if isinstance(root, LvmVolume) else self._get_kernel_params_partition(root)

		# Zswap should be disabled when using zram.
		# https://github.com/archlinux/archinstall/issues/881
		if self._zram:
			kernel_parameters.append('zswap.enabled=0')

		if self._enc.encryption_type != EncryptionType.NO_ENCRYPTION and self._enc.fido2_device:
			# auto, not the enrolled hidraw path: hidraw numbering is not stable across boots.
			# token-timeout: absent token otherwise holds the PIN/token prompt
			# for the 30s default before falling back to the passphrase query
			kernel_parameters.append('rd.luks.options=fido2-device=auto,token-timeout=5,password-echo=no')

		for sub_vol in root.btrfs_subvols:
			if sub_vol.is_root():
				kernel_parameters.append(f'rootflags=subvol={sub_vol.name}')
				break

		kernel_parameters.append('rw')
		kernel_parameters.append(f'rootfstype={root.safe_fs_type.fs_type_mount}')
		kernel_parameters.extend(self._extra_params)

		debug(f'kernel parameters: {" ".join(kernel_parameters)}')
		return kernel_parameters

	def _add_systemd_bootloader(
		self,
		boot_partition: PartitionModification,
		efi_partition: PartitionModification | None,
		uki_enabled: bool,
		removable: bool,
	) -> None:
		debug('Installing systemd bootloader')
		self.dnf.strap(Bootloader.Systemd.packages(uki=uki_enabled))

		if not efi_partition or not efi_partition.mountpoint:
			raise ValueError('Could not detect a mounted EFI system partition')

		bootctl_options = []
		# A UKI is self-contained on the ESP (EFI/Linux), so systemd-boot reads
		# nothing from a separate boot partition. Naming it makes bootctl demand
		# XBOOTLDR typing for no gain
		if not uki_enabled and has_separate_boot(boot_partition, efi_partition):
			bootctl_options.append(f'--esp-path={efi_partition.mountpoint}')
			bootctl_options.append(f'--boot-path={boot_partition.mountpoint}')

		# bootctl detects the chroot as a container and skips the EFI boot
		# variables unless told; --variables=yes forces them. It also writes
		# EFI/BOOT/BOOTX64.EFI, which boots when the NVRAM refuses an entry.
		# anaconda's bootctl call, ESP at /boot/efi there
		# anaconda/pyanaconda/modules/storage/bootloader/systemd.py:150-166
		def _bootctl_install(variables: str) -> None:
			self._inst.arch_chroot(['bootctl', variables, *bootctl_options, 'install'])

		# removable keeps the NVRAM out of it: from an installed host the new
		# entry (same title) replaces the host's own, first in BootOrder
		if removable:
			_bootctl_install('--variables=no')
		else:
			try:
				_bootctl_install('--variables=yes')
			except SysCallError as err:
				warn(f'bootctl could not write EFI variables ({err}), retrying with --variables=no')
				_bootctl_install('--variables=no')

		# kernel-install names entries <machine-id>-<version>, so no default
		# entry is pinned: systemd-boot picks the newest
		loader_conf = self.target / efi_partition.relative_mountpoint / 'loader/loader.conf'
		loader_conf.parent.mkdir(parents=True, exist_ok=True)
		loader_conf.write_text('timeout 5\n')
		debug(f'Wrote {loader_conf}')

	def _add_efistub_bootloader(self, efi_partition: PartitionModification | None, root: PartitionModification | LvmVolume, removable: bool) -> None:
		# the firmware boots one file, so it has to keep its name across kernel
		# updates: a kernel-install plugin copies each new UKI over it.
		# removable, or a firmware refusing the entry, puts that file at the
		# fallback path instead
		debug('Installing efistub bootloader')
		self.dnf.strap(Bootloader.Efistub.packages())

		if not efi_partition or not efi_partition.mountpoint:
			raise ValueError('Could not detect a mounted EFI system partition')

		if removable or not self._register_efistub(efi_partition):
			self._write_efistub_plugin(_efi_fallback())
		self._inst.install_kernels(self._get_kernel_params(root))

	def _register_efistub(self, efi_partition: PartitionModification) -> bool:
		# before the UKI exists: the entry only names a path, and an empty
		# NVRAM slot is cheaper to find out about than a stale plugin
		self._write_efistub_plugin(_EFISTUB_UKI)
		parent_dev_path = get_parent_device_path(efi_partition.safe_dev_path)
		loader = '\\' + _EFISTUB_UKI.replace('/', '\\')
		try:
			self._inst.arch_chroot([
				'efibootmgr', '--create', '--disk', str(parent_dev_path), '--part', str(efi_partition.partn),
				'--label', 'Fedora (efistub)', '--loader', loader,
			])  # fmt: skip
		except SysCallError as err:
			warn(f'efibootmgr could not register the UKI, booting it from {_efi_fallback()} instead: {err}')
			return False
		return True

	def _write_efistub_plugin(self, path: str) -> None:
		plugin = self.target / 'etc/kernel/install.d' / _EFISTUB_PLUGIN
		plugin.parent.mkdir(parents=True, exist_ok=True)
		plugin.write_text(
			textwrap.dedent(f"""\
				#!/bin/sh
				# written by fedinstoo: efistub boots one fixed file, keep it the
				# newest UKI kernel-install built
				[ "$1" = add ] || exit 0
				[ "$KERNEL_INSTALL_LAYOUT" = uki ] || exit 0
				mkdir -p "$KERNEL_INSTALL_BOOT_ROOT/{Path(path).parent}"
				cp "$KERNEL_INSTALL_STAGING_AREA/uki.efi" "$KERNEL_INSTALL_BOOT_ROOT/{path}"
			""")
		)
		plugin.chmod(0o755)
		debug(f'Wrote {plugin} -> {path}')

	def _add_grub_bootloader(
		self,
		boot_partition: PartitionModification,
		efi_partition: PartitionModification | None,
		removable: bool,
		params: list[str],
	) -> None:
		debug('Installing grub bootloader')
		uefi = SysInfo.has_uefi()
		self.dnf.strap(Bootloader.Grub.packages(uefi=uefi))

		self._write_grub_default(params)

		if not uefi:
			parent_dev_path = get_parent_device_path(boot_partition.safe_dev_path)
			info(f'GRUB boot device: {parent_dev_path}')
			try:
				self._inst.arch_chroot(['grub2-install', '--target=i386-pc', '--recheck', str(parent_dev_path)], peek_output=True)
			except SysCallError as err:
				raise DiskError(f'Failed to install GRUB boot on {parent_dev_path}: {err}') from err
			return

		if not efi_partition or efi_partition.mountpoint != GRUB_ESP:
			raise ValueError(f'GRUB on UEFI needs the ESP at {GRUB_ESP}')

		# shim and grubx64.efi come prebuilt and signed from the RPMs, so no
		# grub2-install on UEFI: only the stub grub.cfg on the ESP that hands
		# over to /boot/grub2/grub.cfg, as Fedora's own installs carry
		# https://docs.fedoraproject.org/en-US/quick-docs/grub2-bootloader/#install-the-bootloader-files
		# https://docs.fedoraproject.org/en-US/quick-docs/grub2-bootloader/#create-a-grub-2-configuration
		self._write_grub_efi_stub()

		# shim-x64 ships EFI/BOOT/BOOTX64.EFI as well: the removable path
		# boots without any entry, so only a registered install needs one
		if removable:
			return

		# TODO: anaconda deletes earlier "Fedora" entries before creating
		# its own; a reinstall here stacks another one in NVRAM
		# anaconda/pyanaconda/modules/storage/bootloader/efi.py:119-159
		parent_dev_path = get_parent_device_path(efi_partition.safe_dev_path)
		loader = r'\EFI\fedora\shimx64.efi'
		try:
			self._inst.arch_chroot([
				'efibootmgr', '--create', '--disk', str(parent_dev_path), '--part', str(efi_partition.partn),
				'--label', 'Fedora', '--loader', loader,
			])  # fmt: skip
		except SysCallError as err:
			# firmware refused the NVRAM entry (full, read-only): EFI/BOOT needs none
			warn(f'efibootmgr could not register GRUB, relying on EFI/BOOT/BOOTX64.EFI: {err}')

	def _write_grub_default(self, params: list[str]) -> None:
		# anaconda writes this, no package ships it. grub2-mkconfig rewrites
		# every BLS entry's options as root=UUID=<fs> ro + GRUB_CMDLINE_LINUX,
		# so the kernel params go here, minus what it adds itself
		# https://fedoraproject.org/wiki/Changes/BootLoaderSpecByDefault#Config_files_provided_by_kernel,_grub2-switch-to-blscfg,_and_zipl-switch-to-blscfg
		# same keys as anaconda's, minus its serial console and Xen cases
		# anaconda/pyanaconda/modules/storage/bootloader/grub2.py:243-276
		# on btrfs it adds rootflags=subvol= as well
		owned = ('root=', 'rootflags=subvol=')
		cmdline = ' '.join(p for p in params if not p.startswith(owned) and p != 'rw')
		content = textwrap.dedent(f"""\
			GRUB_TIMEOUT=5
			GRUB_DISTRIBUTOR="$(sed 's, release .*$,,g' /etc/system-release)"
			GRUB_DEFAULT=saved
			GRUB_DISABLE_SUBMENU=true
			GRUB_TERMINAL_OUTPUT="console"
			GRUB_CMDLINE_LINUX="{cmdline}"
			GRUB_DISABLE_RECOVERY="true"
			GRUB_ENABLE_BLSCFG=true
		""")
		grub_default = self.target / 'etc/default/grub'
		grub_default.parent.mkdir(parents=True, exist_ok=True)
		grub_default.write_text(content)
		debug(f'Wrote {grub_default}')

	def _write_grub_efi_stub(self) -> None:
		# grub2 reads its real config from the filesystem holding /boot: a
		# separate one is its own root, otherwise /boot sits in the root fs,
		# under the root subvolume on btrfs (FSROOT). Same stub grub2's
		# gen_grub_cfgstub writes, which anaconda runs
		# anaconda/pyanaconda/modules/storage/bootloader/efi.py:195-205
		# JSON: the target's own self-bind stacks under the root fs with no
		# UUID, and splitting plain columns shifted its FSROOT into the UUID
		# slot. Mountinfo order puts the visible (topmost) mount last
		boot = self.target / 'boot'
		out = SysCommand(['findmnt', '-J', '-l', '-o', 'UUID,FSROOT,TARGET', '--target', str(boot)]).decode()
		fs = json.loads(out)['filesystems'][-1]
		uuid, fsroot, mountpoint = fs['uuid'], fs['fsroot'].rstrip('/'), Path(fs['target'])
		prefix = f'{fsroot}/grub2' if mountpoint == boot else f'{fsroot}/boot/grub2'

		stub = self.target / GRUB_ESP.relative_to('/') / _GRUB_EFI_DIR / 'grub.cfg'
		stub.parent.mkdir(parents=True, exist_ok=True)
		stub.write_text(
			textwrap.dedent(f"""\
				search --no-floppy --root-dev-only --fs-uuid --set=dev {uuid}
				set prefix=($dev){prefix}
				export $prefix
				configfile $prefix/grub.cfg
			""")
		)
		debug(f'Wrote {stub}')

	def _grub_mkconfig(self) -> None:
		# grubenv, then grub.cfg, as anaconda orders them
		# anaconda/pyanaconda/modules/storage/bootloader/grub2.py:325-373
		grubenv = self.target / 'boot/grub2/grubenv'
		try:
			if not grubenv.exists():
				self._inst.arch_chroot(['grub2-editenv', '/boot/grub2/grubenv', 'create'])
			self._inst.arch_chroot(['grub2-mkconfig', '-o', '/boot/grub2/grub.cfg'])
		except SysCallError as err:
			raise DiskError(f'Could not configure GRUB: {err}') from err
