# Pre-mounted layouts with a LUKS root: lsblk hangs the filesystem and the
# mountpoint on the dm-crypt child, not on the partition, so the root was
# never found. https://github.com/archlinux/archinstall/issues/4182

from pathlib import Path

from archinstoo.lib.disk.device_handler import luks_child_mount
from archinstoo.lib.models.device import (
	DeviceModification,
	DiskEncryption,
	EncryptionType,
	LsblkInfo,
	ModificationStatus,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	Unit,
)

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
