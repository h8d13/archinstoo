from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from archinstoo.lib.exceptions import RequirementError, SysCallError
from archinstoo.lib.pm import pacman
from archinstoo.lib.pm.pacman import Pacman

if TYPE_CHECKING:
	from collections.abc import Callable


def _failing(*failures: Exception) -> tuple[list[int], Callable[[], None]]:
	calls: list[int] = []
	pending = list(failures)

	def func() -> None:
		calls.append(1)
		if pending:
			raise pending.pop(0)

	return calls, func


def _answers(monkeypatch: pytest.MonkeyPatch, *answers: str) -> None:
	remaining = list(answers)
	monkeypatch.setattr(pacman, '_can_prompt', lambda: True)
	monkeypatch.setattr(pacman, '_SILENT', False)
	monkeypatch.setattr('builtins.input', lambda _q: remaining.pop(0))


def test_silent_fails_without_asking(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(pacman, '_SILENT', True)
	monkeypatch.setattr(pacman, '_can_prompt', lambda: True)
	monkeypatch.setattr('builtins.input', pytest.fail)
	_, func = _failing(SysCallError('boom', 1))

	with pytest.raises(RequirementError):
		Pacman(Path('/mnt')).ask('err', 'bail', func)


def test_exit_fails_like_silent(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	_answers(monkeypatch, 'e')
	calls, func = _failing(SysCallError('boom', 1))

	with pytest.raises(RequirementError):
		Pacman(Path('/mnt')).ask('err', 'bail', func)
	assert len(calls) == 1


def _target(tmp_path: Path) -> Path:
	(tmp_path / 'usr/bin').mkdir(parents=True)
	(tmp_path / 'usr/bin/bash').touch()
	return tmp_path


def test_shell_then_retry_until_it_works(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
) -> None:
	shells: list[int] = []
	monkeypatch.setattr(pacman, 'drop_to_shell', lambda _t: shells.append(1))
	_answers(monkeypatch, 'x', 's', '')
	calls, func = _failing(SysCallError('a', 1), SysCallError('b', 1))

	Pacman(_target(tmp_path)).ask('err', 'bail', func)

	assert len(calls) == 3
	assert shells == [1]


@pytest.mark.parametrize('root', [True, False])
def test_no_shell_asks_again_instead_of_retrying(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	root: bool,
) -> None:
	# '/' is the running system; an empty target has no bash to chroot to
	monkeypatch.setattr(pacman, 'drop_to_shell', pytest.fail)
	_answers(monkeypatch, 's', 'e')
	calls, func = _failing(SysCallError('boom', 1))

	with pytest.raises(RequirementError):
		Pacman(Path('/') if root else tmp_path).ask('err', 'bail', func)
	assert len(calls) == 1


def _counting_reset(resets: list[int]) -> Callable[[], bool]:
	# stands in for Pacman.reset_keyring: records the run and reports success
	def reset() -> bool:
		resets.append(1)
		return True

	return reset


def test_sniffed_cause_fixed_before_asking(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	# shows up on the retry, not the first failure: still fixed unasked
	resets: list[int] = []
	monkeypatch.setattr(Pacman, 'reset_keyring', _counting_reset(resets))
	_answers(monkeypatch, 'r')
	calls, func = _failing(
		SysCallError('boom', 1),
		SysCallError('invalid or corrupted package', 1),
	)

	Pacman(Path('/mnt')).ask('err', 'bail', func)

	assert len(calls) == 3
	assert resets == [1]


def test_same_fix_runs_once(monkeypatch: pytest.MonkeyPatch) -> None:
	resets: list[int] = []
	monkeypatch.setattr(Pacman, 'reset_keyring', _counting_reset(resets))
	monkeypatch.setattr(pacman, '_SILENT', True)
	calls, func = _failing(
		SysCallError('signature is invalid', 1),
		SysCallError('gpgme error', 1),
	)

	with pytest.raises(RequirementError):
		Pacman(Path('/mnt')).ask('err', 'bail', func)
	assert len(calls) == 2
	assert resets == [1]


@pytest.mark.parametrize(
	'line',
	[
		'error: keyring is not writable',
		'error: required key missing from keyring',
	],
)
def test_broken_keyring_is_sniffed(line: str) -> None:
	found = pacman._auto_recovery(SysCallError(line, 1))
	assert found
	assert found[1] is Pacman.reset_keyring


def test_package_name_in_argv_is_not_sniffed() -> None:
	err = SysCallError(
		"['pacstrap', 'signstar-request-signature'] exited: target not found",
		1,
		worker_log=b'error: target not found: signstar-request-sig',
	)
	assert pacman._auto_recovery(err) is None
