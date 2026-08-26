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
	Unit,
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
	('boot', 'efi', 'expected'),
	[
		# add_bootloader hands the same object twice when nothing is at /boot
		(ESP_EFI, ESP_EFI, False),
		(ESP_BOOT_EFI, ESP_BOOT_EFI, False),
		# ESP mounted at /boot: both getters return the one partition
		(ESP_BOOT, ESP_BOOT, False),
		# the only layout with a real second partition
		(SEPARATE_BOOT, ESP_EFI, True),
	],
)
def test_has_separate_boot(
	boot: tuple[str, str, list[PartitionFlag]],
	efi: tuple[str, str, list[PartitionFlag]],
	expected: bool,
) -> None:
	assert Installer._has_separate_boot(_part(*boot), _part(*efi)) is expected


def test_has_separate_boot_ignores_obj_id() -> None:
	# _obj_id is a fresh uuid4 per instance and takes part in the dataclass
	# __eq__, so `boot != efi` reported "separate" for two descriptions of one
	# partition. Compare the device instead.
	assert _part(*ESP_BOOT) != _part(*ESP_BOOT)
	assert Installer._has_separate_boot(_part(*ESP_BOOT), _part(*ESP_BOOT)) is False


def test_has_separate_boot_without_esp() -> None:
	assert Installer._has_separate_boot(_part(*SEPARATE_BOOT), None) is False
