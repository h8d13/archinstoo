# The command line, stdlib only: parse_early reads it before bootstrap
# installs what lib.args needs, ArchConfigHandler parses it again after.

import argparse
from pathlib import Path

from archinstoo._version import VERSION

DEFAULT_SCRIPT = 'guided'
# scripts that do not need root access
ROOTLESS_SCRIPTS = frozenset({'list', 'mirror', 'count', 'schema', 'detect', 'dev.vm'})
# scripts that only touch the running system
NO_DISK_SCRIPTS = frozenset({'packages'})

_HELP_FLAGS = frozenset({'-h', '--help'})
# what the host run of --script bootstrap reads itself
_BOOTSTRAP_HOST_ARGS = frozenset(
	{'--script', 'bootstrap', '--script=bootstrap', '--debug'}
)


def script_help(path: Path) -> str:
	# a script's --help is the comment block its file opens with
	lines = []
	for line in path.read_text().splitlines():
		if not line.startswith('#'):
			break
		lines.append(line.removeprefix('#').removeprefix(' '))
	return '\n'.join(lines)


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		formatter_class=argparse.ArgumentDefaultsHelpFormatter, add_help=False
	)
	parser.add_argument(
		'--script',
		nargs='?',
		default=DEFAULT_SCRIPT,
		help='Script to run for installation',
		type=str,
	)
	parser.add_argument(
		'--config',
		type=Path,
		nargs='?',
		default=None,
		help='JSON configuration file',
	)
	parser.add_argument(
		'--config-url',
		type=str,
		nargs='?',
		default=None,
		help='Url to a JSON configuration file',
	)
	parser.add_argument(
		'--dry-run',
		action='store_true',
		default=False,
		help=(
			'Generates a configuration file and then exits instead of '
			'performing an installation'
		),
	)
	parser.add_argument(
		'--mountpoint',
		type=Path,
		nargs='?',
		default=Path('/mnt'),
		help='Define an alternate mount point for installation',
	)
	parser.add_argument(
		'--skip-ntp',
		action='store_true',
		help='Disables NTP checks during installation',
		default=False,
	)
	parser.add_argument(
		'--skip-wkd',
		action='store_true',
		help='Disables checking if archlinux keyring wkd sync is complete.',
		default=False,
	)
	parser.add_argument(
		'--skip-boot',
		action='store_true',
		help=(
			'Disables installation of a boot loader (note: only use this '
			'when problems arise with the boot loader step).'
		),
		default=False,
	)
	parser.add_argument(
		'--debug',
		action='store_true',
		default=False,
		help='Adds debug info into the log',
	)
	parser.add_argument(
		'--offline',
		action='store_true',
		default=False,
		help='Skip db refresh, bootstrap and keyring update.',
	)
	parser.add_argument(
		'--advanced',
		action='store_true',
		default=False,
		help='Enabled advanced options',
	)
	parser.add_argument(
		'--clean',
		action='store_true',
		default=False,
		help='Clean up the log directory on exit',
	)
	parser.add_argument(
		'--silent',
		action='store_true',
		default=False,
		help=(
			'Install straight from --config with no menus or prompts '
			'(unattended)'
		),
	)
	parser.add_argument(
		'--version',
		'-v',
		action='version',
		version=f'archinstoo {VERSION}',
		help='Show version and exit',
	)

	return parser


def parse_early() -> tuple[argparse.Namespace, bool]:
	# the real grammar before any preparation (-v/--version exits here). No
	# default for --script: the bare global help needs "not given" visible
	parser = build_parser()
	parser.set_defaults(script=None)
	early, remaining = parser.parse_known_args()
	# add_help=False: -h stays unparsed, for the global help or the script's
	return early, not _HELP_FLAGS.isdisjoint(remaining)


def bootstrap_argv(argv: list[str]) -> tuple[list[str], list[str]]:
	# (argv for the root, options misplaced before --). What follows --
	# reaches the root as given; before it only -h is forwarded, anything
	# else would be parsed by the host run and never reach the root
	split = argv.index('--') if '--' in argv else len(argv)
	head = argv[:split]
	own = [a for a in head if a in _HELP_FLAGS]
	extra = [a for a in head if a not in _BOOTSTRAP_HOST_ARGS | _HELP_FLAGS]
	return [*own, '--', *argv[split + 1 :]], extra
