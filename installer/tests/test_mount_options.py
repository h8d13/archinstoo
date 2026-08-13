from pathlib import Path

import pytest

from archinstoo.lib.installer import Installer
from archinstoo.lib.models.device import (
	BootMountOption,
	FilesystemType,
	ModificationStatus,
	PartitionFlag,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	Unit,
)

HARDENED = ['nodev', 'nosuid', 'noexec']
BOOT_MEDIA = HARDENED + ['nosymfollow']
MASKS = ['fmask=0177', 'dmask=0077']


def _part(
	mountpoint: str | None,
	fs_type: FilesystemType,
	flags: list[PartitionFlag] | None = None,
	mount_options: list[str] | None = None,
) -> PartitionModification:
	return PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, SectorSize.default()),
		length=Size(512, Unit.MiB, SectorSize.default()),
		fs_type=fs_type,
		mountpoint=Path(mountpoint) if mountpoint else None,
		mount_options=mount_options or [],
		flags=flags or [],
	)


def test_esp_gets_hardening_and_masks() -> None:
	part = _part('/efi', FilesystemType.FAT32, [PartitionFlag.ESP])
	assert Installer._harden_boot_options(part, []) == BOOT_MEDIA + MASKS


def test_xbootldr_gets_hardening_and_masks() -> None:
	part = _part('/boot', FilesystemType.FAT32, [PartitionFlag.XBOOTLDR])
	assert Installer._harden_boot_options(part, []) == BOOT_MEDIA + MASKS


def test_ext4_xbootldr_keeps_nosymfollow_without_masks() -> None:
	# XBOOTLDR is not required to be vfat
	part = _part('/boot', FilesystemType.EXT4, [PartitionFlag.XBOOTLDR])
	assert Installer._harden_boot_options(part, []) == BOOT_MEDIA


def test_plain_boot_keeps_symlinks_and_gets_no_masks() -> None:
	part = _part('/boot', FilesystemType.EXT4)
	assert Installer._harden_boot_options(part, []) == HARDENED


def test_root_and_home_untouched() -> None:
	for mountpoint in ('/', '/home'):
		part = _part(mountpoint, FilesystemType.EXT4)
		assert Installer._harden_boot_options(part, ['rw']) == ['rw']


@pytest.mark.parametrize(
	'option',
	[BootMountOption.dev, BootMountOption.suid, BootMountOption.exec, BootMountOption.symfollow],
)
def test_explicit_opposite_wins(option: BootMountOption) -> None:
	part = _part('/boot', FilesystemType.EXT4, [PartitionFlag.XBOOTLDR], [option.name])
	options = Installer._harden_boot_options(part, [option.name])
	assert option.value not in options
	assert option.name in options


def test_no_duplicates_on_preset_options() -> None:
	part = _part('/efi', FilesystemType.FAT32, [PartitionFlag.ESP], ['nodev', 'fmask=0177'])
	options = Installer._harden_boot_options(part, ['nodev', 'fmask=0177'])
	assert sorted(options) == sorted(BOOT_MEDIA + MASKS)


def test_configured_mask_value_kept() -> None:
	part = _part('/efi', FilesystemType.FAT32, [PartitionFlag.ESP], ['fmask=0022'])
	options = Installer._harden_boot_options(part, ['fmask=0022'])
	assert 'fmask=0022' in options
	assert 'fmask=0177' not in options
