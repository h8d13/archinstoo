# the ESP stub grub.cfg points grub at the filesystem holding /boot. The
# target's self-bind stacks under the root fs with no UUID: findmnt lists
# both, and the stub named the bind (search ... /mnt), dropping every
# GRUB install to the grub shell

import json
from typing import TYPE_CHECKING

import pytest

from archinstoo.lib.bootloader import install
from archinstoo.lib.bootloader.install import BootloaderInstaller

if TYPE_CHECKING:
	from pathlib import Path
	from typing import Any

UUID = '1f16eab5-3faa-4347-b28f-12921b93c5f8'


def _stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filesystems: list[dict[str, Any]]) -> list[str]:
	out = json.dumps({'filesystems': filesystems})
	monkeypatch.setattr(install, 'SysCommand', lambda _cmd: type('Out', (), {'decode': lambda self: out})())
	installer = BootloaderInstaller.__new__(BootloaderInstaller)
	installer.target = tmp_path
	installer._write_grub_efi_stub()
	return (tmp_path / 'boot/efi/EFI/fedora/grub.cfg').read_text().splitlines()[:2]


@pytest.mark.parametrize(
	('filesystems', 'expected'),
	[
		# findmnt --target on a self-bound /mnt, as seen in the VM
		(
			[{'uuid': None, 'fsroot': '/mnt', 'target': '/mnt'}, {'uuid': UUID, 'fsroot': '/', 'target': '/mnt'}],
			[f'search --no-floppy --root-dev-only --fs-uuid --set=dev {UUID}', 'set prefix=($dev)/boot/grub2'],
		),
		# separate /boot: its own root
		(
			[{'uuid': UUID, 'fsroot': '/', 'target': 'BOOT'}],
			[f'search --no-floppy --root-dev-only --fs-uuid --set=dev {UUID}', 'set prefix=($dev)/grub2'],
		),
		# btrfs root subvolume
		(
			[{'uuid': UUID, 'fsroot': '/@', 'target': '/mnt'}],
			[f'search --no-floppy --root-dev-only --fs-uuid --set=dev {UUID}', 'set prefix=($dev)/@/boot/grub2'],
		),
	],
)
def test_stub_names_the_visible_boot_fs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filesystems: list[dict[str, Any]], expected: list[str]) -> None:
	for fs in filesystems:
		if fs['target'] == 'BOOT':
			fs['target'] = str(tmp_path / 'boot')
	assert _stub(tmp_path, monkeypatch, filesystems) == expected
