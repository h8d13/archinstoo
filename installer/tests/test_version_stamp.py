# Drift guard for the version string.
#
# PKGBUILD owns pkgver/pkgrel. _version.py reads them in a checkout and falls
# back to __pkgstamp__, which PKGBUILD build() rewrites via sed for the wheel.
# These tests fail if a literal version creeps back into the source, or if the
# sed expressions stop matching the line they stamp (which would ship a package
# reporting 0.0.0-0).

import re
from pathlib import Path

import pytest

from archinstoo._version import __pkgstamp__, __version__, read_pkgbuild_version

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
