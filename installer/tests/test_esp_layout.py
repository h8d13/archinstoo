from pathlib import Path

import pytest

from archinstoo.lib.disk.layouts import _boot_partition
from archinstoo.lib.models.bootloader import Bootloader
from archinstoo.lib.models.device import FilesystemType, PartitionFlag, SectorSize, Unit

SECTOR = SectorSize(512, Unit.B)


@pytest.mark.parametrize(
	('bootloader', 'using_subvolumes', 'expected'),
	[
		# Fedora's shim and grub RPMs install into /boot/efi, whatever the root fs
		(Bootloader.Grub, True, '/boot/efi'),
		(Bootloader.Grub, False, '/boot/efi'),
		# systemd-boot reads FAT only: the ESP is /boot, or /efi with
		# subvolumes so /boot stays in @ (UKI)
		(Bootloader.Systemd, True, '/efi'),
		(Bootloader.Systemd, False, '/boot'),
	],
)
def test_uefi_esp_mountpoint(bootloader: Bootloader, using_subvolumes: bool, expected: str) -> None:
	parts = _boot_partition(
		SECTOR,
		using_gpt=True,
		uefi=True,
		bootloader=bootloader,
		filesystem_type=FilesystemType.BTRFS,
		using_subvolumes=using_subvolumes,
	)
	assert len(parts) == 1
	assert parts[0].mountpoint == Path(expected)
	assert parts[0].fs_type == FilesystemType.FAT32
	assert PartitionFlag.ESP in parts[0].flags


def test_bios_grub_gets_bios_grub_partition_on_gpt() -> None:
	parts = _boot_partition(
		SECTOR,
		using_gpt=True,
		uefi=False,
		bootloader=Bootloader.Grub,
		filesystem_type=FilesystemType.EXT4,
	)
	assert PartitionFlag.BIOS_GRUB in parts[0].flags
	boot = next(p for p in parts if p.mountpoint == Path('/boot'))
	assert boot.fs_type == FilesystemType.EXT4
