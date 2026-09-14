# Pre-mounted layouts with a LUKS root: lsblk hangs the filesystem and the
# mountpoint on the dm-crypt child, not on the partition, so the root was
# never found. https://github.com/archlinux/archinstall/issues/4182

from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.disk.device_handler import DeviceHandler, luks_child_mount
from archinstoo.lib.models.device import (
	BDevice,
	DeviceModification,
	DiskEncryption,
	EncryptionType,
	FilesystemType,
	LsblkInfo,
	ModificationStatus,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	Unit,
	_DeviceInfo,
)

if TYPE_CHECKING:
	from collections.abc import Mapping

# lsblk --json -o NAME,PATH,PKNAME,TYPE,FSTYPE,UUID,PARTUUID,MOUNTPOINTS /dev/vda2
# on the dev VM after `cryptsetup open /dev/vda2 encrypted_p2 && mount /dev/mapper/encrypted_p2 /mnt`
LUKS_OPEN = {
	'name': 'vda2',
	'path': '/dev/vda2',
	'pkname': 'vda',
	'type': 'part',
	'fstype': 'crypto_LUKS',
	'uuid': '999197b3-bcea-4f0e-9772-d3cef34abc10',
	'partuuid': 'a3a38bb4-cbe1-4540-9815-feea03ab6339',
	'mountpoints': [],
	'children': [
		{
			'name': 'encrypted_p2',
			'path': '/dev/mapper/encrypted_p2',
			'pkname': 'vda2',
			'type': 'crypt',
			'fstype': 'ext4',
			'uuid': 'f10af165-0d0f-49bd-81f6-d40de4fbe06e',
			'partuuid': None,
			'mountpoints': ['/mnt'],
		}
	],
}


def test_luks_child_mount_follows_crypt_child() -> None:
	child = luks_child_mount(LsblkInfo.from_dict(LUKS_OPEN), Path('/mnt'))
	assert child is not None
	assert child.name == 'encrypted_p2'
	assert child.fstype == 'ext4'


def test_luks_child_mount_ignores_other_base() -> None:
	assert luks_child_mount(LsblkInfo.from_dict(LUKS_OPEN), Path('/other')) is None


def test_luks_child_mount_closed_container() -> None:
	closed = {**LUKS_OPEN, 'children': []}
	assert luks_child_mount(LsblkInfo.from_dict(closed), Path('/mnt')) is None


def _part(mapper: str | None) -> PartitionModification:
	sector = SectorSize(512, Unit.B)
	return PartitionModification(
		status=ModificationStatus.EXIST,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, sector),
		length=Size(1, Unit.GiB, sector),
		dev_path=Path('/dev/vda2'),
		mountpoint=Path('/'),
		luks_mapper=mapper,
	)


def _mods(*parts: PartitionModification) -> list[DeviceModification]:
	# DeviceModification wants a BDevice; only .partitions is read here
	mod = DeviceModification.__new__(DeviceModification)
	mod.partitions = list(parts)
	return [mod]


def test_pre_mounted_encryption_marks_luks_partitions() -> None:
	root = _part('encrypted_p2')
	enc = DiskEncryption.from_pre_mounted(_mods(root))
	assert enc is not None
	assert enc.encryption_type == EncryptionType.LUKS
	assert enc.partitions == [root]
	assert enc.encryption_password is None
	assert enc.is_pre_mounted()


def test_pre_mounted_encryption_plain_layout() -> None:
	assert DiskEncryption.from_pre_mounted(_mods(_part(None))) is None


# lsblk --json -o NAME,PATH,PKNAME,TYPE,FSTYPE,UUID,PARTUUID,MOUNTPOINTS /dev/md0
# on the dev VM: RAID1 over vda2+vda3, LUKS on the array, ext4 in the mapper.
# The array carries no partition table, so nothing here hangs off a partition.
RAID_LUKS_OPEN = {
	'name': 'md0',
	'path': '/dev/md0',
	'pkname': None,
	'type': 'raid1',
	'fstype': 'crypto_LUKS',
	'uuid': 'dfeeea05-36e6-4d1a-8738-46a59f3ca921',
	'partuuid': None,
	'mountpoints': [],
	'children': [
		{
			'name': 'raid_root',
			'path': '/dev/mapper/raid_root',
			'pkname': 'md0',
			'type': 'crypt',
			'fstype': 'ext4',
			'uuid': '59bc3fd8-1f5d-4fb8-a08e-b2a011b60918',
			'partuuid': None,
			'mountpoints': ['/mnt'],
		}
	],
}


def _device(path: str) -> BDevice:
	sector = SectorSize(512, Unit.B)
	info = _DeviceInfo(
		model='md',
		path=Path(path),
		type='raid1',
		total_size=Size(8379392, Unit.B, sector),
		free_space_regions=[],
		sector_size=sector,
		read_only=False,
		dirty=False,
	)
	# BDevice wants a parted Disk; only device_info is read here
	device = BDevice.__new__(BDevice)
	device.device_info = info
	device.partition_infos = []
	return device


def _whole_device(lsblk: Mapping[str, object], base: Path = Path('/mnt')) -> PartitionModification | None:
	# __init__ scans the host's real disks through pyparted
	handler = DeviceHandler.__new__(DeviceHandler)
	handler._lsblk_info = lambda path: LsblkInfo.from_dict(dict(lsblk))  # type: ignore[method-assign,assignment]
	return handler._pre_mounted_whole_device(_device('/dev/md0'), base)


def test_whole_device_follows_luks_on_an_array() -> None:
	part_mod = _whole_device(RAID_LUKS_OPEN)

	assert part_mod is not None
	assert part_mod.dev_path == Path('/dev/md0')
	assert part_mod.fs_type == FilesystemType.EXT4
	assert part_mod.mountpoint == Path('/')
	assert part_mod.luks_mapper == 'raid_root'
	assert part_mod.on_raid
	# the container's UUID, not the ext4 one: rd.luks.name= wants that one
	assert part_mod.uuid == 'dfeeea05-36e6-4d1a-8738-46a59f3ca921'


def test_whole_device_ignores_other_base() -> None:
	assert _whole_device(RAID_LUKS_OPEN, Path('/other')) is None


def test_whole_device_plain_filesystem_is_not_flagged_raid() -> None:
	plain = {**RAID_LUKS_OPEN, 'type': 'disk', 'fstype': 'ext4', 'mountpoints': ['/mnt'], 'children': []}
	part_mod = _whole_device(plain)

	assert part_mod is not None
	assert part_mod.mountpoint == Path('/')
	assert part_mod.luks_mapper is None
	assert not part_mod.on_raid


def test_whole_device_unmounted_array_is_skipped() -> None:
	closed = {**RAID_LUKS_OPEN, 'children': []}
	assert _whole_device(closed) is None
