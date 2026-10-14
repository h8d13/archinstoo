from pathlib import Path

import pytest

from archinstoo.lib.models.device import (
	FilesystemType,
	ModificationStatus,
	PartitionFlag,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
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
		# BootloaderInstaller hands the same object twice when nothing is at /boot
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
	# __hash__ reads obj_id raw. __post_init__ used to mint a UUID while
	# parse_arg restored the same identity from json as a str, so one
	# partition hashed into two buckets depending on where it came from.
	part = _part(*ESP_EFI)
	restored = _part(*ESP_EFI)
	restored.obj_id = part.obj_id  # what DiskLayoutConfiguration.parse_arg does

	assert isinstance(part.obj_id, str)
	assert part.obj_id == restored.obj_id
	assert hash(part) == hash(restored)
	assert {part: 'luks'}[restored] == 'luks'
