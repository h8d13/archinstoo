# What the bootloader is told about the disk: root= picks PARTUUID when the
# root has one (an md array has none, and wrote root=PARTUUID=None), and the
# systemd-boot NVRAM entry names its ESP explicitly where bootctl cannot

from pathlib import Path

import pytest

from archinstoo.lib.bootloader import install
from archinstoo.lib.bootloader.install import BootloaderInstaller
from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.models.device import (
	DiskEncryption,
	FilesystemType,
	ModificationStatus,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	Unit,
)

SECTOR = SectorSize(512, Unit.B)


def _root(partuuid: str | None) -> PartitionModification:
	return PartitionModification(
		status=ModificationStatus.EXIST,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.MiB, SECTOR),
		length=Size(1, Unit.GiB, SECTOR),
		mountpoint=Path('/'),
		fs_type=FilesystemType.EXT4,
		dev_path=Path('/dev/md0'),
		partuuid=partuuid,
		uuid='1234-root',
	)


def _installer() -> BootloaderInstaller:
	inst = BootloaderInstaller.__new__(BootloaderInstaller)
	inst._enc = DiskEncryption()
	return inst


@pytest.mark.parametrize(
	('partuuid', 'expected'),
	[('abcd-part', 'root=PARTUUID=abcd-part'), (None, 'root=UUID=1234-root')],
)
def test_root_by_partuuid_or_uuid(partuuid: str | None, expected: str) -> None:
	assert _installer()._get_kernel_params_partition(_root(partuuid)) == [expected]


@pytest.mark.parametrize(
	('arch', 'bitness', 'loader'),
	[('x86_64', 64, 'x64'), ('x86_64', 32, 'ia32'), ('aarch64', 64, 'aa64')],
)
def test_systemd_boot_entry_names_the_esp(
	monkeypatch: pytest.MonkeyPatch, arch: str, bitness: int, loader: str
) -> None:
	# the bootstrap root has no systemd mode: bootctl wrote a zeroed ESP GUID
	# there, efibootmgr takes disk and partition explicitly
	calls: list[list[str]] = []
	monkeypatch.setattr(SysInfo, 'arch', staticmethod(lambda: arch))
	monkeypatch.setattr(SysInfo, 'bitness', staticmethod(lambda: bitness))
	monkeypatch.setattr(
		install, 'get_parent_device_path', lambda _path: Path('/dev/vda')
	)
	monkeypatch.setattr(install, 'SysCommand', calls.append)
	esp = _root('abcd-part')
	esp.dev_path = Path('/dev/vda1')
	esp.partn = 1

	_installer()._register_systemd_boot(esp)

	assert calls == [
		[
			'efibootmgr',
			'--create',
			'--disk',
			'/dev/vda',
			'--part',
			'1',
			'--label',
			'Linux Boot Manager',
			'--loader',
			f'\\EFI\\systemd\\systemd-boot{loader}.efi',
			'--unicode',
		],
	]
