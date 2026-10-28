# A reinstall marks the old ESP and root DELETE beside the new ones, and the
# menu sorts deleted entries first: lookups must not land on them.

from pathlib import Path

import pytest

from archinstoo.lib.disk.partitioning_menu import FreeSpace
from archinstoo.lib.models.device import (
	BDevice,
	DeviceModification,
	FilesystemType,
	ModificationStatus,
	PartitionFlag,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	Unit,
	_DeviceInfo,
)

S512 = SectorSize(512, Unit.B)


def _part(
	status: ModificationStatus, start_mib: int, mountpoint: str, esp: bool = False
) -> PartitionModification:
	return PartitionModification(
		status=status,
		type=PartitionType.PRIMARY,
		start=Size(start_mib, Unit.MiB, S512),
		length=Size(512, Unit.MiB, S512),
		fs_type=FilesystemType.FAT32 if esp else FilesystemType.EXT4,
		mountpoint=Path(mountpoint),
		flags=[PartitionFlag.ESP] if esp else [],
		dev_path=Path(f'/dev/vda{start_mib}')
		if status != ModificationStatus.CREATE
		else None,
	)


def test_lookups_skip_deleted_partitions() -> None:
	old_esp = _part(ModificationStatus.DELETE, 1, '/boot', esp=True)
	old_root = _part(ModificationStatus.DELETE, 513, '/')
	new_esp = _part(ModificationStatus.CREATE, 2049, '/boot', esp=True)
	new_root = _part(ModificationStatus.CREATE, 2561, '/')
	info = _DeviceInfo(
		'stub',
		Path('/dev/vda'),
		'disk',
		Size(8, Unit.GiB, S512),
		[],
		S512,
		False,
		False,
	)
	mod = DeviceModification(
		device=BDevice(disk=None, device_info=info, partition_infos=[]),  # type: ignore[arg-type]
		wipe=False,
		partitions=[old_esp, old_root, new_esp, new_root],
	)

	assert mod.get_efi_partition() is new_esp
	assert mod.get_boot_partition() is new_esp
	assert mod.get_root_partition() is new_root


def test_gap_too_small_once_aligned_is_not_offered() -> None:
	# 1 MiB + 1 sector between off-grain neighbours: no whole MiB fits
	gap = FreeSpace(Size(2049, Unit.sectors, S512), Size(4098, Unit.sectors, S512))
	assert not gap.length > Size(1, Unit.MiB, S512)


def test_create_needs_a_length() -> None:
	with pytest.raises(ValueError, match='must have a length'):
		PartitionModification(
			status=ModificationStatus.CREATE,
			type=PartitionType.PRIMARY,
			start=Size(1, Unit.MiB, S512),
			length=Size(0, Unit.B, S512),
		)
