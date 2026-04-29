from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import DiskError, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.models.device import (
	DiskEncryption,
	DiskLayoutConfiguration,
	EncryptionType,
	FilesystemType,
)
from archinstoo.lib.output import info, warn

from .luks import Luks2

if TYPE_CHECKING:
	from .device_handler import DeviceHandler


def swapoff_path(path: Path | None) -> None:
	if path is None:
		return
	with suppress(SysCallError, DiskError):
		SysCommand(['swapoff', str(path)])


def swapoff_layout(disk_config: DiskLayoutConfiguration) -> None:
	for mod in disk_config.device_modifications:
		for part in mod.partitions:
			if part.is_swap():
				swapoff_path(part.dev_path)
				if part.mapper_name:
					swapoff_path(Path('/dev/mapper') / part.mapper_name)

	lvm_cfg = disk_config.lvm_config
	if not lvm_cfg:
		return

	for vol in lvm_cfg.get_all_volumes():
		if vol.fs_type == FilesystemType.LINUX_SWAP:
			swapoff_path(vol.dev_path)
			if vol.mapper_name:
				swapoff_path(Path('/dev/mapper') / vol.mapper_name)


def close_luks(dev_path: Path, mapper_name: str | None) -> None:
	if mapper_name is None:
		return
	Luks2(dev_path, mapper_name=mapper_name).lock()


def teardown_layout(
	target: Path,
	disk_config: DiskLayoutConfiguration,
	disk_encryption: DiskEncryption,
	device_handler: DeviceHandler,
) -> None:
	# Order: swapoff, unmount, deactivate VGs, close LUKS. Inner mappers close before the
	# outer ones that hold them.
	info('Tearing down target mounts and mappings')

	swapoff_layout(disk_config)

	try:
		SysCommand(['umount', '-R', str(target)])
	except SysCallError:
		warn(f'{target} busy, retrying with lazy unmount')
		SysCommand(['umount', '-R', '-l', str(target)])

	lvm_cfg = disk_config.lvm_config

	def _deactivate_vgs() -> None:
		if not lvm_cfg:
			return
		for vg in lvm_cfg.vol_groups:
			device_handler.lvm_vg_deactivate(vg.name)

	match disk_encryption.encryption_type:
		case EncryptionType.LUKS_ON_LVM:
			# LUKS sits on top of LVs, close LUKS first, then deactivate VGs.
			for vol in disk_encryption.lvm_volumes:
				close_luks(vol.safe_dev_path, vol.mapper_name)
			_deactivate_vgs()
		case EncryptionType.LVM_ON_LUKS:
			# VGs sit on LUKS PV, deactivate VGs first, then close LUKS.
			_deactivate_vgs()
			for part in disk_encryption.partitions:
				close_luks(part.safe_dev_path, part.mapper_name)
		case EncryptionType.LUKS:
			for part in disk_encryption.partitions:
				close_luks(part.safe_dev_path, part.mapper_name)
		case EncryptionType.NO_ENCRYPTION:
			_deactivate_vgs()
