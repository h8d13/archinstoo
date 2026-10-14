import shlex
from pathlib import Path

import pytest

from archinstoo.lib import chroot
from archinstoo.lib.chroot import chroot_prefix, run_in_target
from archinstoo.lib.utils.env import Os


@pytest.mark.parametrize(('release', 'expected'), [({'ID': 'fedora', 'VERSION_ID': '44'}, '44'), ({'ID': 'fedora'}, '')])
def test_os_release(monkeypatch: pytest.MonkeyPatch, release: dict[str, str], expected: str) -> None:
	monkeypatch.setattr('platform.freedesktop_os_release', lambda: release)

	assert Os.os_release('VERSION_ID') == expected


def test_os_release_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
	def unreadable() -> dict[str, str]:
		raise OSError('no os-release')

	monkeypatch.setattr('platform.freedesktop_os_release', unreadable)
	assert not Os.os_release('ID')


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


@pytest.fixture
def no_mounts(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
	mounted: list[Path] = []
	monkeypatch.setattr(chroot, 'mount_api', mounted.append)
	return mounted


def test_chroot_prefix_inherits_env(no_mounts: list[Path]) -> None:
	# plain chroot(1): the caller's env (proxies) carries over
	assert chroot_prefix(Path('/mnt')) == ['chroot', '/mnt']
	assert no_mounts == [Path('/mnt')]


@pytest.mark.usefixtures('no_mounts')
def test_run_as_keeps_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
	calls: list[str] = []
	monkeypatch.setattr(chroot, 'SysCommand', lambda cmd, **_: calls.append(cmd))

	run_in_target(Path('/mnt'), 'git clone foo', run_as='alice')

	argv = shlex.split(calls[0])
	assert argv[:2] == ['chroot', '/mnt']
	assert argv[2:4] == ['su', '-w']
	assert set(argv[4].split(',')) >= {'http_proxy', 'https_proxy', 'no_proxy'}
	assert argv[5:] == ['-', 'alice', '-c', 'git clone foo']


def test_mount_api_skips_the_host_root(monkeypatch: pytest.MonkeyPatch) -> None:
	calls: list[list[str]] = []
	monkeypatch.setattr(chroot, 'SysCommand', lambda cmd, **_: calls.append(cmd))

	chroot.mount_api(Path('/'))
	assert calls == []
