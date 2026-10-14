# the VG takes anaconda's name, numbered past one the host already has
import pytest

from archinstoo.lib.disk import lvm


@pytest.mark.parametrize(
	('existing', 'expected'),
	[
		('', 'fedora'),
		('  fedora\n', 'fedora_1'),
		('  fedora\n  fedora_1\n  data\n', 'fedora_2'),
	],
)
def test_free_vg_name(monkeypatch: pytest.MonkeyPatch, existing: str, expected: str) -> None:
	monkeypatch.setattr(lvm, 'SysCommand', lambda cmd: type('Out', (), {'decode': lambda self: existing})())

	assert lvm.free_vg_name() == expected
