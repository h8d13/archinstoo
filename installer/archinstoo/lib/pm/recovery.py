# Halt and ask instead of aborting when an install step fails.
# The caller passes the choices that make sense for its own failure; the two
# that always apply, resolving it by hand in a shell or stopping, are
# appended here. Plain print/input: only used during the install itself,
# never while a menu is on screen.

import contextlib
import os
import re
import subprocess
import sys
import termios
from dataclasses import dataclass

from archinstoo.lib.output import debug, info, stylize, warn

# returned when the user fixed the problem by hand and asked to resume:
# callers handle it on top of their own keys, it means "run it again as is"
RETRY = 'retry'

_MANUAL = '__manual__'
_EXIT = '__exit__'
_VERSIONED = re.compile(r'(?P<name>[^<>=]+)(?P<version>[<>=].*)$')


class InstallationAbortedError(Exception):
	# the user chose to stop from a recovery prompt, or nobody was there to
	# answer one: a decision, not a crash, so no bug report banner
	def __init__(self, reason: str) -> None:
		super().__init__(reason)
		self.reason = reason


@dataclass(frozen=True)
class Recovery:
	key: str  # what prompt() returns when this one is picked
	label: str


def package(spec: str) -> str:
	# a package reference for a Recovery label: 'mesa>=25.0' reads as a
	# name plus a requirement
	if not (match := _VERSIONED.match(spec)):
		return stylize(spec, 'red')
	return stylize(match['name'], 'red') + stylize(match['version'], 'orange')


def prompt(
	header: str,
	options: list[Recovery],
	*,
	detail: str = '',
	hint: str = '',
	interactive: bool = True,
) -> str:
	# returns one of the caller's keys or RETRY. --silent has nobody to
	# answer, so an unattended run stops rather than guessing
	choices = [
		*options,
		Recovery(_MANUAL, 'Resolve manually in a shell'),
		Recovery(_EXIT, 'Exit the installation'),
	]

	if not interactive or not _can_prompt():
		raise InstallationAbortedError(header)

	while True:
		_render(header, detail, choices)
		key = _pick(header, choices)

		if key == _EXIT:
			raise InstallationAbortedError(header)
		if key != _MANUAL:
			return key

		open_shell(hint)
		if confirm('Resume the installation now?'):
			return RETRY


def open_shell(hint: str = '') -> None:
	# hand the terminal over and block until the user leaves the shell
	shell = os.environ.get('SHELL') or '/bin/bash'

	print()
	info(f'Pausing the installation and starting {shell}.')
	if hint:
		print(hint)
	print(stylize("Type 'exit' or press Ctrl+D to return.", 'green'))
	print()

	try:
		subprocess.run([shell], check=False)  # noqa: S603 - the user's $SHELL
	except OSError, KeyboardInterrupt:
		warn(f'Could not run {shell}')

	print()


def ask_text(question: str) -> str:
	# free-form answer, empty on EOF
	return _read_line(question) or ''


def confirm(question: str) -> bool:
	# yes unless told otherwise; EOF counts as no
	answer = _read_line(f'{question} (Y/n): ')
	if answer is None:
		return False
	return answer.lower() in {'', 'y', 'yes'}


def report_dropped(packages: list[str]) -> None:
	# re-listed once the install ends, so a skipped package cannot pass
	# unnoticed between hundreds of lines of pacstrap output
	if not packages:
		return

	warn('These packages were skipped while recovering from errors:')
	for name in packages:
		warn(f' - {name}')
	warn('The installed system may be incomplete, check them before use.')


def _render(header: str, detail: str, choices: list[Recovery]) -> None:
	print()
	print(stylize(header, 'red'))
	for line in detail.splitlines():
		print(f'  {stylize(line, "gray")}')
	print()
	for index, choice in enumerate(choices, 1):
		print(f'  {stylize(str(index), "green")}) {choice.label}')
	print()


def _pick(header: str, choices: list[Recovery]) -> str:
	# a wrong answer asks again on one line: re-rendering the whole block
	# per stray line buried the choices under copies of themselves
	question = f'Select an option [1-{len(choices)}]: '
	while True:
		answer = _read_line(question)
		if answer is None:
			# stdin went away, nothing can be asked anymore
			raise InstallationAbortedError(header)
		if answer.isdigit() and 1 <= int(answer) <= len(choices):
			return choices[int(answer) - 1].key
		if answer:
			print(f'Please enter a number between 1 and {len(choices)}.')


def _can_prompt() -> bool:
	try:
		return sys.stdin.isatty()
	except AttributeError, OSError, ValueError:
		return False


def _read_line(question: str) -> str | None:
	# drop keys pressed while pacstrap was running (an impatient Enter or
	# two): they would otherwise answer this question unseen
	with contextlib.suppress(OSError, ValueError, termios.error):
		termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
	try:
		return input(question).strip()
	except EOFError:
		print()
		debug('stdin closed while waiting for an answer')
		return None
