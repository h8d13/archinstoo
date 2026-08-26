from pathlib import Path

import pytest

from archinstoo.lib import hardware
from archinstoo.lib.bootloader.validation import validate_bootloader
from archinstoo.lib.models.bootloader import Bootloader, BootloaderConfiguration
from archinstoo.lib.models.device import (
	DeviceModification,
	DiskLayoutConfiguration,
	DiskLayoutType,
	FilesystemType,
	ModificationStatus,
	PartitionFlag,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	SubvolumeModification,
	Unit,
)

SECTOR = SectorSize(512, Unit.B)


@pytest.fixture(autouse=True)
def _uefi_host(monkeypatch: pytest.MonkeyPatch) -> None:
	# the validator asks the live system whether it is UEFI; pin it so these
	# cases do not depend on the machine running the suite
	monkeypatch.setattr(hardware.SysInfo, 'has_uefi', staticmethod(lambda: True))


def _part(
	mountpoint: str | None,
	dev_path: str,
	fs: FilesystemType | None,
	flags: list[PartitionFlag],
	*,
	subvols: bool = False,
) -> PartitionModification:
	part = PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, SECTOR),
		length=Size(1, Unit.GiB, SECTOR),
		mountpoint=Path(mountpoint) if mountpoint else None,
		fs_type=fs,
		flags=flags,
		dev_path=Path(dev_path),
	)
	if subvols:
		part.btrfs_subvols = [SubvolumeModification(Path('@'), Path('/'))]
	return part


ESP_EFI = _part('/efi', '/dev/vda1', FilesystemType.FAT32, [PartitionFlag.ESP])
ESP_BOOT = _part('/boot', '/dev/vda1', FilesystemType.FAT32, [PartitionFlag.ESP, PartitionFlag.BOOT])
BOOT_FLAGGED = _part('/boot', '/dev/vda2', FilesystemType.FAT32, [PartitionFlag.BOOT])
BOOT_XBOOTLDR = _part('/boot', '/dev/vda2', FilesystemType.FAT32, [PartitionFlag.XBOOTLDR])
BOOT_EXT4 = _part('/boot', '/dev/vda2', FilesystemType.EXT4, [PartitionFlag.XBOOTLDR])
ROOT_BTRFS = _part('/', '/dev/vda3', FilesystemType.BTRFS, [], subvols=True)


def _errors(bootloader: Bootloader, parts: list[PartitionModification], *, uki: bool = False) -> list[str]:
	disk_config = DiskLayoutConfiguration(
		config_type=DiskLayoutType.Manual,
		device_modifications=[DeviceModification(device=None, wipe=True, partitions=parts)],  # type: ignore[arg-type]
	)
	return validate_bootloader(BootloaderConfiguration(bootloader, uki=uki), disk_config, uefi=True)


def test_systemd_xbootldr_accepted() -> None:
	# row I: the only layout that legitimately gets --boot-path
	assert _errors(Bootloader.Systemd, [ESP_EFI, BOOT_XBOOTLDR, ROOT_BTRFS]) == []


def test_systemd_boot_flagged_rejected() -> None:
	# row K: BOOT sets the ESP type GUID, bootctl demands XBOOTLDR and the
	# install dies after pacstrap
	errors = _errors(Bootloader.Systemd, [ESP_EFI, BOOT_FLAGGED, ROOT_BTRFS])
	assert 'A separate /boot for systemd-boot must be marked XBOOTLDR' in errors


def test_systemd_boot_flagged_allowed_under_uki() -> None:
	# row J: a UKI is self-contained on the ESP, bootctl is never told about
	# the boot partition, so the XBOOTLDR rule does not apply
	assert _errors(Bootloader.Systemd, [ESP_EFI, BOOT_FLAGGED, ROOT_BTRFS], uki=True) == []


def test_systemd_non_fat_xbootldr_rejected() -> None:
	errors = _errors(Bootloader.Systemd, [ESP_EFI, BOOT_EXT4, ROOT_BTRFS])
	assert 'systemd-boot requires a FAT /boot partition' in errors


def test_systemd_esp_at_efi_without_boot_needs_uki() -> None:
	errors = _errors(Bootloader.Systemd, [ESP_EFI, ROOT_BTRFS])
	assert 'systemd-boot with ESP at /efi requires UKI or a separate XBOOTLDR /boot partition' in errors


def test_limine_esp_at_boot_accepted() -> None:
	# row O: kernels land on the FAT ESP, which is all limine can read
	assert _errors(Bootloader.Limine, [ESP_BOOT, ROOT_BTRFS]) == []


def test_limine_separate_fat_boot_accepted() -> None:
	# row M
	assert _errors(Bootloader.Limine, [ESP_EFI, BOOT_XBOOTLDR, ROOT_BTRFS]) == []


def test_limine_esp_at_efi_rejected() -> None:
	# row P: nothing at /boot means the kernels are on btrfs and limine
	# panics at first boot. The previous condition could never fire.
	errors = _errors(Bootloader.Limine, [ESP_EFI, ROOT_BTRFS])
	assert any('Limine requires kernels on a FAT partition' in e for e in errors)


def test_limine_esp_at_efi_allowed_under_uki() -> None:
	assert _errors(Bootloader.Limine, [ESP_EFI, ROOT_BTRFS], uki=True) == []


def test_grub_esp_at_efi_accepted() -> None:
	# rows A/D/E: grub reads btrfs, so /boot staying in @ is fine
	assert _errors(Bootloader.Grub, [ESP_EFI, ROOT_BTRFS]) == []
