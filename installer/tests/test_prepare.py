# _prepare syncs the db and fetches deps before argparse exists. On an Arch
# host (H2T) that pair is a partial upgrade of the user's own system, so it
# must not run there; the ISO and the distros/BOOT root are throwaway.

import pytest

import archinstoo
from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.pm.pacman import Pacman
from archinstoo.lib.utils.env import Os


@pytest.mark.parametrize(
	('distro_id', 'on_iso', 'bootstrap', 'arch_host'),
	[
		('arch', False, False, True),
		('archarm', False, False, True),
		('arch', True, False, False),
		('arch', False, True, False),
		('debian', False, False, False),
	],
)
def test_arch_host(
	monkeypatch: pytest.MonkeyPatch,
	distro_id: str,
	on_iso: bool,
	bootstrap: bool,
	arch_host: bool,
) -> None:
	monkeypatch.setattr('platform.freedesktop_os_release', lambda: {'ID': distro_id})
	monkeypatch.setattr(Os, 'running_from_host', staticmethod(lambda: not on_iso))
	monkeypatch.setattr(Os, 'running_from_bootstrap', staticmethod(lambda: bootstrap))

	assert Os.running_from_arch_host() is arch_host


@pytest.mark.parametrize(('arch_host', 'synced'), [(True, False), (False, True)])
def test_prepare_skips_pacman_on_arch_host(
	monkeypatch: pytest.MonkeyPatch,
	arch_host: bool,
	synced: bool,
) -> None:
	calls: list[str] = []
	monkeypatch.setattr('sys.argv', ['archinstoo'])
	monkeypatch.delenv('A2_DEPS_FETCHED', raising=False)
	monkeypatch.setattr(archinstoo, 'is_root', lambda: True)
	monkeypatch.setattr(archinstoo, '_log_env_info', lambda: None)
	monkeypatch.setattr(archinstoo, '_check_online', lambda: 0)
	monkeypatch.setattr(Os, 'running_from_arch_host', staticmethod(lambda: arch_host))
	monkeypatch.setattr(Os, 'running_from_foreign', staticmethod(lambda: False))
	monkeypatch.setattr(Pacman, 'run', staticmethod(lambda args, **_: calls.append(args)))

	assert archinstoo._prepare() == 0
	assert ('-Syy' in calls) is synced
	assert any(call.startswith('-T') for call in calls) is synced


def _deptest_exits(monkeypatch: pytest.MonkeyPatch, code: int, log: bytes) -> None:
	def run(args: str, **_: object) -> None:
		raise SysCallError(f'pacman {args}', code, worker_log=log)

	monkeypatch.setattr(Pacman, 'run', staticmethod(run))


@pytest.mark.parametrize(
	('code', 'log', 'missing'),
	[
		# 127: pacman names what is unsatisfied, pty noise is dropped
		(127, b'warning: noise\r\nlvm2\r\ngit\r\n', ['lvm2', 'git']),
		# any other exit: pacman itself failed, nothing known about the deps
		(1, b'error: config file could not be read\r\n', None),
		# 127 naming nothing we asked about: unreadable, not satisfied
		(127, b'\r\n', None),
	],
)
def test_missing_deps_exit_codes(
	monkeypatch: pytest.MonkeyPatch,
	code: int,
	log: bytes,
	missing: list[str] | None,
) -> None:
	_deptest_exits(monkeypatch, code, log)
	depends = ('git', 'lvm2', 'pacman')

	if missing is None:
		with pytest.raises(SysCallError):
			archinstoo._missing_deps(depends)
	else:
		assert archinstoo._missing_deps(depends) == missing


def test_bootstrap_fails_on_broken_deptest(monkeypatch: pytest.MonkeyPatch) -> None:
	# a failed -T used to read as "satisfied" and mark deps fetched
	_deptest_exits(monkeypatch, 1, b'error: failed to initialize alpm library\r\n')
	monkeypatch.delenv('A2_DEPS_FETCHED', raising=False)

	assert archinstoo._bootstrap() == 1
	assert not Os.has_env('A2_DEPS_FETCHED')
