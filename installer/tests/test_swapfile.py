# hibernation needs a swap file on the root filesystem; not every fs can
# host one. bcachefs accepts mkswap --file and then fails swapon with EINVAL,
# so the installer has to bow out before the file and fstab line exist
from typing import TYPE_CHECKING

import pytest

from archinstoo.lib import hardware
from archinstoo.lib import installer as installer_mod
from archinstoo.lib import swap as swap_mod
from archinstoo.lib.exceptions import DiskError
from archinstoo.lib.installer import Installer
from archinstoo.lib.models.swap import SwapConfiguration

if TYPE_CHECKING:
	from pathlib import Path


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


def test_bcachefs_refuses_before_touching_the_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	installation, chroot = _session(tmp_path, monkeypatch, 'bcachefs')

	with pytest.raises(DiskError, match='bcachefs'):
		swap_mod.setup_swapfile(installation, 4)

	assert chroot == []
	assert installation._fstab_entries == []


def test_bcachefs_hibernation_degrades_to_a_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# setup_swap keeps the finished install: zram still comes up, only the
	# swap file is skipped
	installation, chroot = _session(tmp_path, monkeypatch, 'bcachefs')
	warned: list[str] = []
	monkeypatch.setattr(installer_mod, 'warn', warned.append)

	installation.setup_swap(SwapConfiguration(zram=True, hibernation=True))

	assert chroot == []
	assert any('bcachefs' in msg for msg in warned)


def test_ext4_swapfile_lands_in_fstab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	installation, chroot = _session(tmp_path, monkeypatch, 'ext4')

	fstab_entry, kernel_params = swap_mod.setup_swapfile(installation, 4)

	assert chroot == [['mkswap', '-U', 'clear', '--size', '4G', '--file', '/swapfile']]
	assert fstab_entry == '/swapfile\tnone\tswap\tdefaults\t0\t0'
	assert kernel_params == []
