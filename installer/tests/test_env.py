import pytest

from archinstoo.lib.utils.env import Os


@pytest.mark.parametrize(
	('distro_id', 'is_arch'),
	[
		('arch', True),
		# Arch Linux ARM, per PKGBUILDs core/filesystem/os-release
		('archarm', True),
		('debian', False),
		('', False),
	],
)
def test_running_from_arch(monkeypatch: pytest.MonkeyPatch, distro_id: str, is_arch: bool) -> None:
	monkeypatch.setattr('platform.freedesktop_os_release', lambda: {'ID': distro_id})

	assert Os.running_from_arch() is is_arch
