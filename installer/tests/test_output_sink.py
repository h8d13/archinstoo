# log lines go to whoever owns the screen: the TUI registers itself while
# curses is up, and output.py never imports it

import logging
from typing import TYPE_CHECKING

from archinstoo.lib import output

if TYPE_CHECKING:
	import pytest


def test_lines_reach_the_registered_sink(
	monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
	monkeypatch.setattr(output, '_supports_color', lambda: False)
	shown: list[str] = []

	output.set_sink(shown.append)
	try:
		output.info('on screen')
	finally:
		output.set_sink()

	assert shown == ['on screen']
	assert not capsys.readouterr().out


def test_no_sink_prints_to_stdout(
	monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
	monkeypatch.setattr(output, '_supports_color', lambda: False)

	output.info('in the shell')

	assert capsys.readouterr().out == 'in the shell\n'


def test_debug_stays_off_screen(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(output, 'log_level', logging.DEBUG)
	shown: list[str] = []

	output.set_sink(shown.append)
	try:
		output.debug('file only')
	finally:
		output.set_sink()

	assert not shown
