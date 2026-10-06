import shlex
from pathlib import Path

import pytest

from archinstoo.lib import chroot
from archinstoo.lib.chroot import chroot_prefix, run_in_target
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


def test_chroot_prefix_inherits_env() -> None:
	# no -S: systemd-run would drop the caller's env (proxies) on the floor
	assert chroot_prefix(Path('/mnt')) == ['arch-chroot', '/mnt']


def test_run_as_keeps_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
	calls: list[str] = []
	monkeypatch.setattr(chroot, 'SysCommand', lambda cmd, **_: calls.append(cmd))

	run_in_target(Path('/mnt'), 'grimoire install foo', run_as='alice')

	argv = shlex.split(calls[0])
	assert argv[:2] == ['arch-chroot', '/mnt']
	assert argv[2:4] == ['su', '-w']
	assert set(argv[4].split(',')) >= {'http_proxy', 'https_proxy', 'no_proxy'}
	assert argv[5:] == ['-', 'alice', '-c', 'grimoire install foo']
