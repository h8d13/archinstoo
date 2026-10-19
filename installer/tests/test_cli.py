# The early parse: run before bootstrap, it decides help, root and prepare.

import pytest

from archinstoo.lib.cli import parse_early


@pytest.mark.parametrize(
	('argv', 'script', 'is_help'),
	[
		# bare run: no --script given, distinct from the guided default
		([], None, False),
		# global help
		(['-h'], None, True),
		# the script's own help, left for it to print
		(['--script', 'list', '--help'], 'list', True),
		# a script's own flags pass through unparsed
		(['--script', 'dev.vm', '--foo'], 'dev.vm', False),
	],
)
def test_parse_early(
	monkeypatch: pytest.MonkeyPatch,
	argv: list[str],
	script: str | None,
	is_help: bool,
) -> None:
	monkeypatch.setattr('sys.argv', ['archinstoo', *argv])

	early, help_given = parse_early()

	assert early.script == script
	assert help_given is is_help
