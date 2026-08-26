from pathlib import Path

import pytest

from archinstoo.lib.installer import Installer
from archinstoo.lib.models.device import (
	FilesystemType,
	ModificationStatus,
	PartitionFlag,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	SubvolumeModification,
	Unit,
	has_separate_boot,
)

SECTOR = SectorSize(512, Unit.B)


def _part(mountpoint: str, dev_path: str, flags: list[PartitionFlag]) -> PartitionModification:
	return PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, SECTOR),
		length=Size(1, Unit.GiB, SECTOR),
		mountpoint=Path(mountpoint),
		fs_type=FilesystemType.FAT32,
		flags=flags,
		dev_path=Path(dev_path),
	)


ESP_EFI = ('/efi', '/dev/vda1', [PartitionFlag.ESP])
ESP_BOOT = ('/boot', '/dev/vda1', [PartitionFlag.ESP, PartitionFlag.BOOT])
ESP_BOOT_EFI = ('/boot/efi', '/dev/vda1', [PartitionFlag.ESP])
SEPARATE_BOOT = ('/boot', '/dev/vda2', [PartitionFlag.BOOT])


@pytest.mark.parametrize(
	('layout', 'shared'),
	[
		# add_bootloader hands the same object twice when nothing is at /boot
		(ESP_EFI, True),
		(ESP_BOOT_EFI, True),
		# ESP mounted at /boot: both getters return that one partition
		(ESP_BOOT, True),
	],
)
def test_no_separate_boot_when_one_partition(layout: tuple[str, str, list[PartitionFlag]], shared: bool) -> None:
	part = _part(*layout)
	assert has_separate_boot(part, part) is not shared


def test_separate_boot_when_two_partitions() -> None:
	assert has_separate_boot(_part(*SEPARATE_BOOT), _part(*ESP_EFI)) is True


def test_has_separate_boot_is_identity() -> None:
	# both getters return elements of one partition list, so the same
	# partition is always the same object; dev_path cannot be used instead
	# because it is still None everywhere before partitioning runs
	esp = _part(*ESP_BOOT)
	assert has_separate_boot(esp, esp) is False
	unpartitioned = PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, SECTOR),
		length=Size(1, Unit.GiB, SECTOR),
		mountpoint=Path('/boot'),
		fs_type=FilesystemType.FAT32,
		flags=[PartitionFlag.BOOT],
	)
	assert unpartitioned.dev_path is None
	assert has_separate_boot(unpartitioned, esp) is True


def test_has_separate_boot_without_esp() -> None:
	assert has_separate_boot(_part(*SEPARATE_BOOT), None) is False


def test_obj_id_hash_survives_a_config_round_trip() -> None:
	# __hash__ reads _obj_id raw. __post_init__ used to mint a UUID while
	# parse_arg restored the same identity from json as a str, so one
	# partition hashed into two buckets depending on where it came from.
	part = _part(*ESP_EFI)
	restored = _part(*ESP_EFI)
	restored._obj_id = part.obj_id  # what DiskLayoutConfiguration.parse_arg does

	assert isinstance(part._obj_id, str)
	assert part.obj_id == restored.obj_id
	assert hash(part) == hash(restored)
	assert {part: 'luks'}[restored] == 'luks'


DEFAULT_SUBVOLS = [('@', '/'), ('@home', '/home'), ('@log', '/var/log'), ('@pkg', '/var/cache/pacman/pkg')]


def _btrfs_root(subvols: list[tuple[str, str]] | None) -> PartitionModification:
	part = PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, SECTOR),
		length=Size(8, Unit.GiB, SECTOR),
		mountpoint=Path('/'),
		fs_type=FilesystemType.BTRFS,
		flags=[],
		dev_path=Path('/dev/vda2'),
	)
	if subvols is not None:
		part.btrfs_subvols = [SubvolumeModification(Path(name), Path(mp)) for name, mp in subvols]
	return part


@pytest.mark.parametrize(
	('boot_on_root', 'subvols', 'expected'),
	[
		# ESP at /boot or a separate /boot partition: kernels at the top
		(False, DEFAULT_SUBVOLS, '\\'),
		(False, None, '\\'),
		# btrfs root, no default subvolume is ever set, so @ is in the path
		(True, DEFAULT_SUBVOLS, '@\\boot\\'),
		(True, [('@root', '/'), ('@home', '/home')], '@root\\boot\\'),
		# btrfs with nothing mounted at /, and non-btrfs roots
		(True, [('@home', '/home')], '\\boot\\'),
		(True, None, '\\boot\\'),
	],
)
def test_refind_kernel_dir(boot_on_root: bool, subvols: list[tuple[str, str]] | None, expected: str) -> None:
	assert Installer._refind_kernel_dir(_btrfs_root(subvols), boot_on_root=boot_on_root) == expected


def test_refind_initrd_matches_installed_system() -> None:
	# byte-for-byte what a real refind + ESP-at-/efi + btrfs install wrote
	kernel_dir = Installer._refind_kernel_dir(_btrfs_root(DEFAULT_SUBVOLS), boot_on_root=True)
	assert f'initrd={kernel_dir}initramfs-linux.img' == 'initrd=@\\boot\\initramfs-linux.img'
