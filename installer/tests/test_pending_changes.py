# The pre-format countdown used to say "Starting device modifications" and nothing
# else. https://github.com/archlinux/archinstall/issues/2334

from pathlib import Path

from archinstoo.lib.disk.filesystem import pending_changes
from archinstoo.lib.models.device import (
	BDevice,
	DeviceModification,
	FilesystemType,
	ModificationStatus,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	Unit,
	_DeviceInfo,
)

SECTOR = SectorSize.default()


def _device(path: str) -> BDevice:
	info = _DeviceInfo('stub', Path(path), 'gpt', Size(64, Unit.GiB, SECTOR), [], SECTOR, False, False)
	return BDevice(disk=None, device_info=info, partition_infos=[])  # type: ignore[arg-type]


def _part(status: ModificationStatus, fs: FilesystemType | None, mnt: str | None, dev: str | None, gib: int = 1) -> PartitionModification:
	return PartitionModification(
		status=status,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, SECTOR),
		length=Size(gib, Unit.GiB, SECTOR),
		fs_type=fs,
		mountpoint=Path(mnt) if mnt else None,
		dev_path=Path(dev) if dev else None,
	)


def test_wipe_is_one_line() -> None:
	mod = DeviceModification(_device('/dev/vda'), wipe=True, partitions=[_part(ModificationStatus.CREATE, FilesystemType.EXT4, '/', None)])
	assert pending_changes([mod]) == ['Pending disk changes:', '  wipe    /dev/vda (every partition on it)']


def test_manual_layout_lists_touched_partitions_only() -> None:
	mod = DeviceModification(
		_device('/dev/nvme0n1'),
		wipe=False,
		partitions=[
			_part(ModificationStatus.EXIST, FilesystemType.NTFS, None, '/dev/nvme0n1p3'),
			_part(ModificationStatus.MODIFY, FilesystemType.FAT32, '/boot', '/dev/nvme0n1p1'),
			_part(ModificationStatus.DELETE, FilesystemType.EXT4, None, '/dev/nvme0n1p5'),
			_part(ModificationStatus.CREATE, FilesystemType.BTRFS, '/', None, gib=40),
		],
	)
	assert pending_changes([mod]) == [
		'Pending disk changes:',
		'  format  /dev/nvme0n1p1 fat32 /boot',
		'  delete  /dev/nvme0n1p5 ext4',
		'  create  /dev/nvme0n1 +40 GiB btrfs /',
	]
