# A failed strap halts and asks instead of ending the install. The two ways
# out that always apply (a shell, or exit) are appended to the caller's,
# a retry only happens when something changed, and --silent stops instead of
# guessing, as archinstoo always did.

import sys
import termios
from pathlib import Path

import pytest

from archinstoo.lib.exceptions import RequirementError, SysCallError
from archinstoo.lib.pm import pacman, recovery
from archinstoo.lib.pm.pacman import Pacman
from archinstoo.lib.pm.recovery import (
	RETRY,
	InstallationAbortedError,
	Recovery,
	prompt,
)

OPTIONS = [
	Recovery('keep_first', 'Keep the first one'),
	Recovery('drop', 'Keep neither and continue'),
]

JACK = b':: jack2 and pipewire-jack are in conflict (jack)\n'
SIGNATURE = b'error: jack2: signature from "x" is unknown trust\n'


@pytest.fixture(autouse=True)
def _interactive(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(recovery, '_can_prompt', lambda: True)
	monkeypatch.setattr(recovery, 'open_shell', lambda _hint='': None)
	monkeypatch.setattr(pacman, '_SILENT', False)
	monkeypatch.setattr(pacman, 'live', lambda path: path)


def _answers(monkeypatch: pytest.MonkeyPatch, *lines: str | None) -> None:
	remaining = list(lines)
	monkeypatch.setattr(recovery, '_read_line', lambda _q: remaining.pop(0))


def _pacstrap(monkeypatch: pytest.MonkeyPatch, *failures: bytes) -> list[str]:
	# each call fails with the next recorded output, then succeeds
	calls: list[str] = []
	pending = list(failures)

	def run(cmd: str, **_: object) -> None:
		calls.append(cmd)
		if pending:
			raise SysCallError(
				'pacstrap failed', 1, worker_log=pending.pop(0)
			)

	monkeypatch.setattr(pacman, 'SysCommand', run)
	return calls


def test_selecting_an_option_returns_its_key(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	_answers(monkeypatch, 'yes', '', '9', '1')

	assert prompt('Package conflict', OPTIONS) == 'keep_first'


def test_wrong_answers_do_not_redraw_the_choices(
	monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
	# stray Enters from the pacstrap run used to stack copies of the block
	_answers(monkeypatch, '', '', '', 'nope', '2')

	assert prompt('Package conflict', OPTIONS) == 'drop'

	out = capsys.readouterr().out
	assert out.count('Package conflict') == 1
	assert out.count('Please enter a number') == 1


def test_keys_pressed_before_the_question_are_discarded(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	flushed: list[int] = []
	monkeypatch.setattr(termios, 'tcflush', lambda _fd, how: flushed.append(how))
	monkeypatch.setattr('builtins.input', lambda _q: '1')
	monkeypatch.setattr(sys.stdin, 'fileno', lambda: 0, raising=False)

	assert recovery._read_line('Select an option [1-4]: ') == '1'
	assert flushed == [termios.TCIFLUSH]


def test_exit_is_always_the_last_choice(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	_answers(monkeypatch, '4')

	with pytest.raises(InstallationAbortedError) as raised:
		prompt('Package conflict', OPTIONS)

	assert raised.value.reason == 'Package conflict'


def test_resolving_manually_then_resuming_retries(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	_answers(monkeypatch, '3', 'y')

	assert prompt('Package conflict', OPTIONS) == RETRY


def test_declining_to_resume_shows_the_choices_again(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	_answers(monkeypatch, '3', 'n', '2')

	assert prompt('Package conflict', OPTIONS) == 'drop'


def test_a_closed_stdin_stops_instead_of_looping(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	_answers(monkeypatch, None)

	with pytest.raises(InstallationAbortedError):
		prompt('Package conflict', OPTIONS)


def test_unattended_runs_stop_without_asking(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	monkeypatch.setattr(pacman, '_SILENT', True)
	_pacstrap(monkeypatch, JACK)

	with pytest.raises(InstallationAbortedError):
		Pacman(Path('/mnt')).strap(['jack2', 'pipewire-jack'])


def test_keeping_one_side_of_a_conflict_retries_without_the_other(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	calls = _pacstrap(monkeypatch, JACK)
	_answers(monkeypatch, '1')
	pm = Pacman(Path('/mnt'))

	pm.strap(['base', 'jack2', 'pipewire-jack'])

	assert len(calls) == 2
	assert 'pipewire-jack' not in calls[1]
	assert pm.dropped_packages == ['pipewire-jack']
	# pipewire-jack may already be on the target from an earlier step:
	# keeping jack2 has to let pacman replace it, not just skip asking
	assert calls[1].endswith('--ask=4')


def test_dropping_both_never_removes_anything_from_the_target(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	calls = _pacstrap(monkeypatch, JACK)
	_answers(monkeypatch, '3')

	Pacman(Path('/mnt')).strap(['base', 'jack2', 'pipewire-jack'])

	assert '--ask' not in ' '.join(calls)


def test_a_dependency_conflict_offers_to_skip_once_a_fix_did_not_help(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	# neither side was asked for: only shell/exit first, then after the
	# same failure again, skipping the rest is the one way forward
	calls = _pacstrap(monkeypatch, JACK, JACK)
	_answers(monkeypatch, '1', 'y', '1')
	pm = Pacman(Path('/mnt'))

	pm.strap(['base', 'pro-audio'])

	assert len(calls) == 2
	assert pm.dropped_packages == ['base', 'pro-audio']


def test_exiting_after_a_repeated_failure_stops(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	_pacstrap(monkeypatch, JACK, JACK)
	# shell, resume; then the repeated failure is answered with exit
	_answers(monkeypatch, '1', 'y', '3')

	with pytest.raises(InstallationAbortedError):
		Pacman(Path('/mnt')).strap(['base', 'pro-audio'])


def test_a_keyring_reset_runs_once_before_asking(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	resets: list[str] = []

	def reset_keyring() -> bool:
		resets.append('keyring')
		return True

	monkeypatch.setattr(Pacman, 'reset_keyring', reset_keyring)
	calls = _pacstrap(monkeypatch, SIGNATURE, SIGNATURE)
	_answers(monkeypatch, '1')

	Pacman(Path('/mnt')).strap(['jack2'])

	assert resets == ['keyring']
	assert len(calls) == 3


def test_skipping_unknown_failures_reports_the_packages(
	monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
	_pacstrap(monkeypatch, b'error: mirror exploded\n')
	_answers(monkeypatch, '2')
	pm = Pacman(Path('/mnt'))

	pm.strap(['jack2'])
	recovery.report_dropped(pm.dropped_packages)

	assert pm.dropped_packages == ['jack2']
	assert 'jack2' in capsys.readouterr().out


def test_keeping_a_package_that_cannot_be_renamed_gives_up(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	# rename with no answer changes nothing, so the original error surfaces
	_pacstrap(monkeypatch, b'error: target not found: jack3\n')
	_answers(monkeypatch, '1', '')

	with pytest.raises(RequirementError):
		Pacman(Path('/mnt')).strap(['jack3'])
