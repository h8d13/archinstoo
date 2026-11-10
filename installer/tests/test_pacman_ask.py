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


def test_shell_then_retry_until_it_works(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	shells: list[int] = []
	monkeypatch.setattr(pacman, 'drop_to_shell', lambda _t: shells.append(1))
	_answers(monkeypatch, 'x', 's', '')
	calls, func = _failing(SysCallError('a', 1), SysCallError('b', 1))

	Pacman(Path('/mnt')).ask('err', 'bail', func)

	assert len(calls) == 3
	assert shells == [1]
