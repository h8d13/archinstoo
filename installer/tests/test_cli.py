# The early parse: run before bootstrap, it decides help, root and prepare.

from dataclasses import fields

import pytest

from archinstoo.lib.cli import Arguments, build_parser, parse_early


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


def test_arguments_mirror_parser() -> None:
	# ArchConfigHandler builds Arguments(**vars(namespace)): a flag added to
	# one side only is a TypeError at startup, or a field no flag can set
	parsed = vars(build_parser().parse_args([]))

	assert set(parsed) == {f.name for f in fields(Arguments)}
