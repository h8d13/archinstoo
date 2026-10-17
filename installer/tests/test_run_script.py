# `--script X` imports archinstoo.scripts.X for its side effects. A missing
# script is a usage error (exit 1 with a hint). A missing import *inside* a
# script used to be swallowed by the same handler: exit 0, nothing run.

from unittest import mock

import pytest

from archinstoo.lib import checkpoints


def _raise_missing(name: str) -> None:
	raise ModuleNotFoundError(f'No module named {name!r}', name=name)


def test_missing_script_exits_with_hint() -> None:
	with mock.patch('importlib.import_module', _raise_missing), pytest.raises(SystemExit) as exc:
		checkpoints._run_script('nope')
	assert exc.value.code == 1


def test_missing_import_inside_script_propagates() -> None:
	def import_module(_name: str) -> None:
		_raise_missing('yaml')

	with mock.patch('importlib.import_module', import_module), pytest.raises(ModuleNotFoundError, match='yaml'):
		checkpoints._run_script('guided')


def test_nested_script_resolves_to_subpackage() -> None:
	with mock.patch('importlib.import_module') as import_module:
		checkpoints._run_script('dev.vm')
	import_module.assert_called_once_with('archinstoo.scripts.dev.vm')


@pytest.mark.parametrize('missing', ['archinstoo.scripts.dev', 'archinstoo.scripts.dev.vm'])
def test_missing_namespace_or_nested_script_exits_with_hint(missing: str) -> None:
	def import_module(_name: str) -> None:
		_raise_missing(missing)

	with mock.patch('importlib.import_module', import_module), pytest.raises(SystemExit) as exc:
		checkpoints._run_script('dev.vm')
	assert exc.value.code == 1


def test_missing_import_inside_nested_script_propagates() -> None:
	def import_module(_name: str) -> None:
		_raise_missing('archinstoo.scripts.other')

	with mock.patch('importlib.import_module', import_module), pytest.raises(ModuleNotFoundError):
		checkpoints._run_script('dev.vm')


@pytest.mark.parametrize('script', ['', '.', 'dev/', 'dev/vm', '../guided', 'dev..vm', 'my-script'])
def test_malformed_name_exits_with_hint(script: str) -> None:
	with mock.patch('importlib.import_module') as import_module, pytest.raises(SystemExit) as exc:
		checkpoints._run_script(script)
	assert exc.value.code == 1
	import_module.assert_not_called()
