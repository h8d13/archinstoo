from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib import checkpoints

if TYPE_CHECKING:
	import pytest


def _capture(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[str]]:
	warned: list[str] = []
	logged: list[str] = []
	monkeypatch.setattr(checkpoints, 'warn', warned.append)
	monkeypatch.setattr(checkpoints, 'log', lambda msg, **_: logged.append(msg))
	return warned, logged


def test_unreached_steps_are_named(monkeypatch: pytest.MonkeyPatch) -> None:
	warned, logged = _capture(monkeypatch)

	checkpoints.report_outcome(Path('/mnt'), {'base': False})

	assert ' - base' in warned
	assert not logged


def test_all_steps_reached_suggests_a_reboot(monkeypatch: pytest.MonkeyPatch) -> None:
	warned, logged = _capture(monkeypatch)

	checkpoints.report_outcome(Path('/mnt'), {'base': True})

	assert not warned
	assert 'You may reboot when ready.' in logged[0]


def test_live_target_does_not_suggest_a_reboot(monkeypatch: pytest.MonkeyPatch) -> None:
	_, logged = _capture(monkeypatch)

	checkpoints.report_outcome(Path('/'), {'base': True})

	assert 'Changes are live on the running system.' in logged[0]
