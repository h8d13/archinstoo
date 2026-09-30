from pathlib import Path

import pytest

from archinstoo.lib.chroot import chroot_prefix
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


@pytest.mark.parametrize(
	('same_root', 'in_chroot'),
	[
		(True, False),
		(False, True),
		# /proc/1/root unreadable (not root): assume no chroot
		(PermissionError(), False),
	],
)
def test_running_in_chroot(monkeypatch: pytest.MonkeyPatch, same_root: bool | OSError, in_chroot: bool) -> None:
	def samefile(self: Path, other: str) -> bool:
		if isinstance(same_root, OSError):
			raise same_root
		return same_root

	monkeypatch.setattr(Path, 'samefile', samefile)

	assert Os.running_in_chroot() is in_chroot


@pytest.mark.parametrize(
	('is_arch', 'booted', 'in_chroot', 'wants_s'),
	[
		# Arch host or ISO
		(True, True, False, True),
		# distros/BOOT: Arch tarball, host /run bound in, host PID1 elsewhere
		(True, True, True, False),
		# Alpine, OpenRC
		(False, False, False, False),
		# Debian/Fedora: systemd, but no promise of >= 257
		(False, True, False, False),
	],
)
def test_chroot_prefix_systemd_mode(
	monkeypatch: pytest.MonkeyPatch,
	is_arch: bool,
	booted: bool,
	in_chroot: bool,
	wants_s: bool,
) -> None:
	monkeypatch.setattr(Os, 'running_from_arch', lambda: is_arch)
	monkeypatch.setattr(Os, 'running_in_chroot', lambda: in_chroot)
	monkeypatch.setattr(Path, 'is_dir', lambda self: booted)

	assert ('-S' in chroot_prefix(Path('/mnt'))) is wants_s
