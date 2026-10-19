# The command line, stdlib only: run_as_a_module parses it before bootstrap
# installs what lib.args needs, ArchConfigHandler parses it again after.

import argparse
from pathlib import Path

from archinstoo._version import VERSION

DEFAULT_SCRIPT = 'guided'


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
