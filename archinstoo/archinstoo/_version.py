import subprocess


def git_shash() -> str:
	return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()  # noqa: S607 - git from $PATH


def git_branch() -> str:
	return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode('ascii').strip()  # noqa: S607 - git from $PATH

__gitstat__ = f'{git_branch()}-{git_shash()}'
__license__ = '- Copyright (C) 2026 - Hadean Eon'
__version__ = f'0.1.13-4 ({__gitstat__}) {__license__}'
