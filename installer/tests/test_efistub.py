from pathlib import Path
from unittest.mock import Mock

import pytest

from archinstoo.lib.bootloader import install
from archinstoo.lib.bootloader.install import BootloaderInstaller
from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.hardware import SysInfo
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
KERNELS = ['linux', 'linux-lts']


def _part(
	dev_path: str,
	partn: int,
	mountpoint: str,
	flags: list[PartitionFlag],
	fs: FilesystemType = FilesystemType.FAT32,
) -> PartitionModification:
	return PartitionModification(
		status=ModificationStatus.EXIST,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, SECTOR),
		length=Size(1, Unit.GiB, SECTOR),
		mountpoint=Path(mountpoint),
		fs_type=fs,
		flags=flags,
		dev_path=Path(dev_path),
		partn=partn,
	)


def _layout(layout: str) -> tuple[PartitionModification, PartitionModification]:
	# (boot, esp) as BootloaderInstaller._partitions() hands them over: with
	# nothing at /boot the ESP stands in for it
	if layout == 'shared':
		esp = _part(
			'/dev/vda1', 1, '/boot', [PartitionFlag.ESP, PartitionFlag.BOOT]
		)
		return esp, esp
	esp_dev = '/dev/vdb1' if layout == 'different-disk' else '/dev/vda1'
	esp = _part(esp_dev, 1, '/efi', [PartitionFlag.ESP])
	boot = _part('/dev/vda2', 2, '/boot', [PartitionFlag.BOOT])
	return boot, esp


def _installer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BootloaderInstaller:
	inst = BootloaderInstaller.__new__(BootloaderInstaller)
	inst.target = tmp_path
	inst.kernels = KERNELS
	inst.pacman = Mock()
	monkeypatch.setattr(
		inst, '_get_kernel_params', lambda _root: ['root=/dev/vda3']
	)
	monkeypatch.setattr(
		install, 'get_parent_device_path', lambda path: Path(str(path)[:-1])
	)
	return inst


@pytest.mark.parametrize('uki_enabled', [False, True])
@pytest.mark.parametrize('layout', ['shared', 'separate', 'different-disk'])
def test_efistub_entry_targets_image_partition(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	uki_enabled: bool,
	layout: str,
) -> None:
	# efibootmgr(8): --disk/--part are the partition containing the loader.
	# The UKI is written to the ESP, a plain kernel to /boot
	boot, esp = _layout(layout)
	inst = _installer(tmp_path, monkeypatch)
	command = Mock()
	monkeypatch.setattr(install, 'SysCommand', command)

	inst._add_efistub_bootloader(boot, esp, Mock(), uki_enabled)

	image = esp if uki_enabled else boot
	assert command.call_count == len(KERNELS)
	for kernel, call in zip(KERNELS, command.call_args_list, strict=True):
		args = call.args[0]
		assert args[args.index('--disk') + 1] == str(image.safe_dev_path)[:-1]
		assert args[args.index('--part') + 1] == str(image.partn)
		assert args[args.index('--loader') + 1] == (
			f'/EFI/Linux/arch-{kernel}.efi'
			if uki_enabled
			else f'/vmlinuz-{kernel}'
		)


def test_efistub_uki_fallback_copies_from_esp(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	# NVRAM refused the entry: the removable-path copy has to read the UKI
	# from the ESP, not from the separate /boot
	boot, esp = _layout('separate')
	inst = _installer(tmp_path, monkeypatch)
	uki = tmp_path / 'efi/EFI/Linux/arch-linux.efi'
	uki.parent.mkdir(parents=True)
	uki.write_text('uki')
	monkeypatch.setattr(
		install, 'SysCommand', Mock(side_effect=SysCallError('nvram', 1))
	)
	monkeypatch.setattr(SysInfo, 'arch', staticmethod(lambda: 'x86_64'))

	inst._add_efistub_bootloader(boot, esp, Mock(), uki_enabled=True)

	assert (tmp_path / 'efi/EFI/BOOT/BOOTX64.EFI').read_text() == 'uki'
