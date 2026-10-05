# hibernation needs a swap file on the root filesystem
from typing import TYPE_CHECKING

from archinstoo.lib import hardware
from archinstoo.lib import installer as installer_mod
from archinstoo.lib.installer import Installer
from archinstoo.lib.kernel import swap as swap_mod

if TYPE_CHECKING:
	from pathlib import Path

	import pytest


def _session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fs_type: str) -> tuple[Installer, list[list[str]]]:
	installation = Installer.__new__(Installer)
	installation.target = tmp_path
	installation._fstab_entries = []
	installation._kernel_params = []
	installation._zram_enabled = False
	chroot: list[list[str]] = []
	monkeypatch.setattr(installation, 'arch_chroot', chroot.append, raising=False)
	monkeypatch.setattr(installer_mod, 'setup_zram', lambda *_: None)

	class FakeCmd:
		def __init__(self, cmd: list[str]) -> None:
			assert cmd[:2] == ['findmnt', '-no']

		def decode(self) -> str:
			return fs_type + '\n'

	monkeypatch.setattr(swap_mod, 'SysCommand', FakeCmd)
	monkeypatch.setattr(hardware.SysInfo, 'has_uefi', staticmethod(lambda: True))
	return installation, chroot


def test_ext4_swapfile_lands_in_fstab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	installation, chroot = _session(tmp_path, monkeypatch, 'ext4')

	fstab_entry, kernel_params = swap_mod.setup_swapfile(installation, 4)

	assert chroot == [['mkswap', '-U', 'clear', '--size', '4G', '--file', '/swapfile']]
	assert fstab_entry == '/swapfile\tnone\tswap\tdefaults\t0\t0'
	assert kernel_params == []
