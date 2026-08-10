import subprocess
from pathlib import Path

# PKGBUILD is the only place a version literal is written. In a checkout we
# read it directly, so nothing here can drift; the stamp below is only what an
# installed wheel falls back to (no PKGBUILD next to site-packages), and
# PKGBUILD build() rewrites it via sed before building.
__pkgstamp__ = '0.1.14-1'

_PKGBUILD = Path(__file__).parents[2] / 'PKGBUILD'


def read_pkgbuild_version() -> str | None:
	# pkgver/pkgrel are plain unquoted assignments at column 0 in both PKGBUILDs.
	fields: dict[str, str] = {}
	try:
		lines = _PKGBUILD.read_text().splitlines()
	except OSError:
		return None

	for line in lines:
		key, sep, value = line.partition('=')
		if sep and key in ('pkgname', 'pkgver', 'pkgrel'):
			fields.setdefault(key, value.strip())

	# guard against picking up an unrelated PKGBUILD that happens to sit there
	if not fields.get('pkgname', '').startswith('archinstoo'):
		return None
	if 'pkgver' not in fields or 'pkgrel' not in fields:
		return None

	return f'{fields["pkgver"]}-{fields["pkgrel"]}'


# -C pins both queries to THIS source tree. without it git inherited the process
# cwd, so an installed archinstoo reported whichever repo you happened to be
# standing in (and DEV anywhere outside one), instead of its own build.
_SRC = str(_PKGBUILD.parent)


def git_shash() -> str:
	return subprocess.check_output(['git', '-C', _SRC, 'rev-parse', '--short', 'HEAD'], stderr=subprocess.DEVNULL).decode('ascii').strip()  # noqa: S603,S607 - fixed argv, git from $PATH


def git_branch() -> str:
	return subprocess.check_output(['git', '-C', _SRC, 'rev-parse', '--abbrev-ref', 'HEAD'], stderr=subprocess.DEVNULL).decode('ascii').strip()  # noqa: S603,S607 - fixed argv, git from $PATH


# installed package: no git binary (OSError) or not a repo (CalledProcessError)
try:
	__gitstat__ = f'{git_branch()}-{git_shash()}'
except OSError, subprocess.CalledProcessError:
	__gitstat__ = 'DEV'

__pkgver__ = read_pkgbuild_version() or __pkgstamp__
__license__ = '- Copyright (C) 2026 - Hadean Eon'
__version__ = f'{__pkgver__} ({__gitstat__}) {__license__}'
