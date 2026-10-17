from pathlib import Path

import pytest

from archinstoo.lib.utils.env import Env


@pytest.mark.parametrize(
	('value', 'default', 'expected'),
	[
		(None, True, True),
		# set but empty is unset, like ${FOO:-default}
		('', True, True),
		('  ', True, True),
		(' Yes ', False, True),
		('0', True, False),
		('nope', True, False),
	],
)
def test_get_bool(monkeypatch: pytest.MonkeyPatch, value: str | None, default: bool, expected: bool) -> None:
	if value is None:
		monkeypatch.delenv('A2_TEST', raising=False)
	else:
		monkeypatch.setenv('A2_TEST', value)

	assert Env.get_bool('A2_TEST', default) is expected


@pytest.mark.parametrize(
	('value', 'base', 'expected'),
	[
		(None, Path('/repo'), None),
		('', Path('/repo'), None),
		('isos/a/x.efi', Path('/repo'), Path('/repo/isos/a/x.efi')),
		# an absolute path ignores base
		('/srv/x.iso', Path('/repo'), Path('/srv/x.iso')),
		('isos/x.iso', None, Path('isos/x.iso')),
	],
)
def test_get_path(monkeypatch: pytest.MonkeyPatch, value: str | None, base: Path | None, expected: Path | None) -> None:
	if value is None:
		monkeypatch.delenv('A2_TEST', raising=False)
	else:
		monkeypatch.setenv('A2_TEST', value)

	assert Env.get_path('A2_TEST', base) == expected


def test_get_path_expands_home(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setenv('HOME', '/home/vm')
	monkeypatch.setenv('A2_TEST', '~/x.iso')

	assert Env.get_path('A2_TEST', Path('/repo')) == Path('/home/vm/x.iso')


@pytest.mark.parametrize(
	('value', 'expected'),
	[
		(None, '4G'),
		# set but empty is unset, like ${FOO:-default}
		('', '4G'),
		('8G', '8G'),
	],
)
def test_get_value(monkeypatch: pytest.MonkeyPatch, value: str | None, expected: str) -> None:
	if value is None:
		monkeypatch.delenv('A2_TEST', raising=False)
	else:
		monkeypatch.setenv('A2_TEST', value)

	assert Env.get_value('A2_TEST', '4G') == expected
	assert Env.get_value('A2_TEST') == (value or None)
