# the package menu's view of the repos, from dnf's own output formats

from typing import TYPE_CHECKING

import pytest

from archinstoo.lib.pm import packages
from archinstoo.lib.pm.dnf import Dnf

if TYPE_CHECKING:
	from collections.abc import Iterator

_REPOQUERY = b"""fedora bash 5.3.0-2.fc44
updates bash 5.3.3-1.fc44
fedora kernel 6.19.5-300.fc44
not-a-row
"""

_INFO = b"""Available packages
Name            : bash
Epoch           : 0
Version         : 5.3.3
Release         : 1.fc44
Architecture    : x86_64
Download size   : 1.9 MiB
Installed size  : 8.4 MiB
Source          : bash-5.3.3-1.fc44.src.rpm
Repository      : updates
Summary         : The GNU Bourne Again shell
URL             : https://www.gnu.org/software/bash
License         : GPL-3.0-or-later
Description     : The GNU Bourne Again shell (Bash) is a shell and command
                : language interpreter.
Vendor          : Fedora Project
"""

_GROUPS = b"""ID                                   Name                                Installed
core                                 Core                                       no
development-tools                    Development Tools                          no
kde-desktop                          KDE                                       yes
"""


class _Out:
	def __init__(self, data: bytes) -> None:
		self._data = data

	def decode(self) -> str:
		return self._data.decode()


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
	packages.list_available_packages.cache_clear()
	packages.list_package_groups.cache_clear()
	yield
	packages.list_available_packages.cache_clear()
	packages.list_package_groups.cache_clear()


def _dnf(monkeypatch: pytest.MonkeyPatch, outputs: dict[str, bytes]) -> list[list[str]]:
	calls: list[list[str]] = []

	def run(args: list[str], **_: object) -> _Out:
		calls.append(args)
		return _Out(outputs[args[0]])

	monkeypatch.setattr(Dnf, 'run', staticmethod(run))
	return calls


def test_listing_keeps_first_row_per_name(monkeypatch: pytest.MonkeyPatch) -> None:
	_dnf(monkeypatch, {'repoquery': _REPOQUERY})
	available = packages.list_available_packages()

	assert set(available) == {'bash', 'kernel'}
	assert available['bash'].repository == 'fedora'
	assert available['kernel'].version == '6.19.5-300.fc44'


def test_listing_failure_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
	def run(args: list[str], **_: object) -> None:
		raise OSError('no network')

	monkeypatch.setattr(Dnf, 'run', staticmethod(run))
	assert packages.list_available_packages() == {}
	assert packages.missing_packages(['nope']) == []


def test_enrich_fills_from_info(monkeypatch: pytest.MonkeyPatch) -> None:
	_dnf(monkeypatch, {'repoquery': _REPOQUERY, 'info': _INFO})
	bash = packages.list_available_packages()['bash']
	packages.enrich_package_info(bash)

	assert bash.summary == 'The GNU Bourne Again shell'
	assert bash.release == '1.fc44'
	assert bash.description == 'The GNU Bourne Again shell (Bash) is a shell and command language interpreter.'
	assert bash.license == 'GPL-3.0-or-later'


def test_groups_are_install_names(monkeypatch: pytest.MonkeyPatch) -> None:
	_dnf(monkeypatch, {'group': _GROUPS})
	groups = packages.list_package_groups()

	assert set(groups) == {'@core', '@development-tools', '@kde-desktop'}
	assert groups['@development-tools'].description == 'Development Tools'


def test_missing_accepts_groups(monkeypatch: pytest.MonkeyPatch) -> None:
	_dnf(monkeypatch, {'repoquery': _REPOQUERY, 'group': _GROUPS})

	assert packages.missing_packages(['bash', '@core', 'linux', '@nope']) == ['linux', '@nope']
