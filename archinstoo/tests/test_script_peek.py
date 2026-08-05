# _script_from_argv decides, before argparse exists, whether a run needs the
# disk half of the deps and whether it needs root. A miss there is silent: the
# right script still runs afterwards, it just got bootstrapped as if it were a
# disk install (pyparted, lvm2, cryptsetup... onto the running system).

import pytest

import archinstoo
from archinstoo.lib.utils.env import Os


@pytest.mark.parametrize(
	('argv', 'expected'),
	[
		(['archinstoo'], None),
		(['archinstoo', '--script', 'packages'], 'packages'),
		(['archinstoo', '--script=packages'], 'packages'),
		(['archinstoo', '--debug', '--script=live', '--offline'], 'live'),
		(['archinstoo', '--script', 'size'], 'size'),
		(['archinstoo', '--script=size'], 'size'),
		# trailing/empty forms: no value to read, fall back to the full path
		(['archinstoo', '--script'], None),
		(['archinstoo', '--script='], None),
		# a value that merely contains the flag name is not the flag
		(['archinstoo', '--config', 'my--script=live.json'], None),
	],
)
def test_script_peek(monkeypatch: pytest.MonkeyPatch, argv: list[str], expected: str | None) -> None:
	monkeypatch.setattr('sys.argv', argv)

	assert archinstoo._script_from_argv() == expected


@pytest.mark.parametrize(
	('script', 'distro_id', 'on_iso', 'blocked'),
	[
		# running-system scripts on a non-Arch root: the case the guard exists for
		('packages', 'debian', False, True),
		('live', 'alpine', False, True),
		# same scripts where target '/' really is Arch
		('packages', 'arch', False, False),
		('live', '', True, False),
		# disk scripts pacstrap a separate target, foreign host or not
		('guided', 'debian', False, False),
		(None, 'debian', False, False),
	],
)
def test_foreign_blocked(
	monkeypatch: pytest.MonkeyPatch,
	script: str | None,
	distro_id: str,
	on_iso: bool,
	blocked: bool,
) -> None:
	monkeypatch.setattr('platform.freedesktop_os_release', lambda: {'ID': distro_id})
	monkeypatch.setattr(Os, 'running_from_host', staticmethod(lambda: not on_iso))

	assert archinstoo._is_foreign_blocked(script) is blocked


@pytest.mark.parametrize('script', sorted(archinstoo.NO_DISK_SCRIPTS | archinstoo.ROOTLESS_SCRIPTS))
def test_both_spellings_agree(monkeypatch: pytest.MonkeyPatch, script: str) -> None:
	# the sets are matched against this peek, so both spellings must land in them
	monkeypatch.setattr('sys.argv', ['archinstoo', f'--script={script}'])
	glued = archinstoo._script_from_argv()

	monkeypatch.setattr('sys.argv', ['archinstoo', '--script', script])
	spaced = archinstoo._script_from_argv()

	assert glued == spaced == script
