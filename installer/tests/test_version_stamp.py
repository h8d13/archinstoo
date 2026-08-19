# Drift guard for the version string.
#
# PKGBUILD owns pkgver/pkgrel. _version.py reads them in a checkout and falls
# back to __pkgstamp__, which PKGBUILD build() rewrites via sed for the wheel.
# These tests fail if a literal version creeps back into the source, or if the
# sed expressions stop matching the line they stamp (which would ship a package
# reporting 0.0.0-0).

import re
import subprocess
from pathlib import Path

import pytest

import archinstoo._version
from archinstoo._version import __pkgstamp__, __version__, git_branch, git_shash, read_pkgbuild_version, resolve_gitstat

ROOT = Path(__file__).parents[2]
PKGBUILDS = (ROOT / 'PKGBUILD', ROOT / 'installer' / 'PKGBUILD')
VERSION_PY = ROOT / 'installer' / 'archinstoo' / '_version.py'


def test_version_comes_from_pkgbuild() -> None:
	pkgver = read_pkgbuild_version()
	assert pkgver is not None, f'{PKGBUILDS[0]} not readable from the checkout'
	assert __version__.startswith(f'{pkgver} (')


def test_stamp_stays_a_placeholder() -> None:
	# a real version here is a second source of truth: it would go stale
	assert __pkgstamp__ == '0.0.0-0'


@pytest.mark.parametrize('pkgbuild', PKGBUILDS, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_sed_stamp_matches_source(pkgbuild: Path) -> None:
	# translate the PKGBUILD's own sed s/// into a python regex and apply it
	sed = re.search(r'sed -i \"s/(?P<pat>.+?)/(?P<repl>.*?)/\" archinstoo/_version\.py', pkgbuild.read_text())
	assert sed, f'no _version.py stamp found in {pkgbuild}'

	stamped, count = re.subn(sed['pat'], 'STAMPED', VERSION_PY.read_text(), flags=re.MULTILINE)
	assert count == 1, f'{pkgbuild} stamp matched {count} lines in _version.py'
	assert 'STAMPED' in stamped


def test_git_stat_describes_this_tree_not_the_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# the version stamp must describe the source it was built from. running git
	# in the process cwd made an installed archinstoo report whatever repo the
	# user happened to stand in, and DEV outside one
	try:
		branch, shash = git_branch(), git_shash()
	except OSError, subprocess.CalledProcessError:
		pytest.skip('not a git checkout, or git unavailable')

	monkeypatch.chdir(tmp_path)  # tmp_path is not a repo
	assert (git_branch(), git_shash()) == (branch, shash)


def test_no_repo_means_rel_when_installed_dev_in_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
	# git always fails around site-packages, so the fallback IS the installed
	# label: releases were reporting DEV
	def _no_repo() -> str:
		raise subprocess.CalledProcessError(128, 'git')

	monkeypatch.setattr(archinstoo._version, 'git_branch', _no_repo)
	assert resolve_gitstat(has_pkgbuild=False) == 'REL'
	assert resolve_gitstat(has_pkgbuild=True) == 'DEV'
