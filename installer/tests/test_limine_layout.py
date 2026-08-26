from pathlib import Path

import pytest

from archinstoo.lib.disk.layouts import _boot_partition
from archinstoo.lib.models.bootloader import Bootloader
from archinstoo.lib.models.device import FilesystemType, PartitionFlag, SectorSize, Unit

SECTOR = SectorSize(512, Unit.B)


@pytest.mark.parametrize(
	('bootloader', 'using_subvolumes', 'expected'),
	[
		# limine reads FAT only, so its kernels have to stay on the ESP even
		# when subvolumes would otherwise move it to /efi
		(Bootloader.Limine, True, '/boot'),
		(Bootloader.Limine, False, '/boot'),
		# everything else keeps /boot inside @ so grub.cfg is snapshotted
		(Bootloader.Grub, True, '/efi'),
		(Bootloader.Systemd, True, '/efi'),
		(Bootloader.Refind, True, '/efi'),
		(Bootloader.Grub, False, '/boot'),
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


def test_bios_limine_boot_stays_fat() -> None:
	# the BIOS branch already carried this rule; pin it alongside the UEFI one
	parts = _boot_partition(
		SECTOR,
		using_gpt=True,
		uefi=False,
		bootloader=Bootloader.Limine,
		filesystem_type=FilesystemType.BTRFS,
	)
	boot = next(p for p in parts if p.mountpoint == Path('/boot'))
	assert boot.fs_type == FilesystemType.FAT32
