# bcachefs left the mainline kernel in 6.18: the stock ISO has no module, so
# the filesystem menu lists it only when /proc/filesystems registers it (a
# medium built with A2_BCACHEFS=1 does, via the dkms oneshot at boot)
from typing import TYPE_CHECKING

from archinstoo.lib import hardware
from archinstoo.lib.disk import selectors
from archinstoo.lib.models.device import FilesystemType

if TYPE_CHECKING:
	from pathlib import Path

	import pytest

	from archinstoo.lib.tui.menu_item import MenuItem

STOCK = 'nodev\tsysfs\nnodev\tproc\n\text4\n\tbtrfs\n\txfs\n'
CUSTOM = STOCK + '\tbcachefs\n'


def _proc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str | None) -> None:
	path = tmp_path / 'filesystems'
	if text is not None:
		path.write_text(text)
	monkeypatch.setattr(hardware, '_PROC_FILESYSTEMS', path)


def _offered(monkeypatch: pytest.MonkeyPatch, advanced: bool) -> list[object]:
	seen: list[MenuItem] = []

	def fake_choice(items: list[MenuItem], **_: object) -> FilesystemType:
		seen.extend(items)
		return FilesystemType.EXT4

	monkeypatch.setattr(selectors, 'prompt_choice', fake_choice)
	selectors.select_main_filesystem_format(advanced=advanced)
	return [item.value for item in seen]


def test_registered_filesystem_is_detected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	_proc(monkeypatch, tmp_path, CUSTOM)
	assert hardware.SysInfo.has_bcachefs()


def test_stock_kernel_has_no_bcachefs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	_proc(monkeypatch, tmp_path, STOCK)
	assert not hardware.SysInfo.has_bcachefs()


def test_missing_proc_reads_as_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	_proc(monkeypatch, tmp_path, None)
	assert not hardware.SysInfo.has_bcachefs()


def test_menu_hides_bcachefs_on_stock_iso(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	_proc(monkeypatch, tmp_path, STOCK)
	offered = _offered(monkeypatch, advanced=True)
	assert FilesystemType.BCACHEFS not in offered
	assert FilesystemType.NTFS in offered


def test_menu_lists_bcachefs_when_registered(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	_proc(monkeypatch, tmp_path, CUSTOM)
	offered = _offered(monkeypatch, advanced=True)
	assert FilesystemType.BCACHEFS in offered


def test_menu_keeps_bcachefs_behind_advanced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	_proc(monkeypatch, tmp_path, CUSTOM)
	assert FilesystemType.BCACHEFS not in _offered(monkeypatch, advanced=False)
