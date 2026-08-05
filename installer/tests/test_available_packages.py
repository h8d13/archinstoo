import re
from pathlib import Path

import pytest

from archinstoo.lib.linux_path import LPath
from archinstoo.lib.models.mirrors import CustomRepository, SignCheck, SignOption
from archinstoo.lib.models.packages import Repository
from archinstoo.lib.pacman import Pacman
from archinstoo.lib.pm import config, packages
from archinstoo.lib.pm.config import PacmanConfig

# `pacman -Sl` on a host with multilib and third-party repos enabled. Repo order
# is conf order; `nano` deliberately appears in two repos.
_SL_OUTPUT = [
	b'core linux 6.19.1.arch1-1\n',
	b'core nano 8.7-1\n',
	b'extra neovim 0.12.2-1\n',
	b'multilib lib32-glibc 2.43-2 [installed]\n',
	b'cachyos nano 8.7-1.1\n',
	b'cachyos ananicy-cpp 1.1.1-3\n',
	b'\n',
]


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
	packages.list_available_packages.cache_clear()


def _stub_pacman(monkeypatch: pytest.MonkeyPatch, output: list[bytes]) -> list[str]:
	calls: list[str] = []

	def run(args: str, **kwargs: object) -> list[bytes]:
		calls.append(args)
		return output if args == '-Sl' else []

	monkeypatch.setattr(Pacman, 'run', staticmethod(run))
	return calls


def test_lists_every_repo_in_the_conf(monkeypatch: pytest.MonkeyPatch) -> None:
	calls = _stub_pacman(monkeypatch, _SL_OUTPUT)

	available = packages.list_available_packages()

	# no repo names passed to pacman: the conf decides
	assert calls == ['-Sy', '-Sl']
	assert set(available) == {'linux', 'nano', 'neovim', 'lib32-glibc', 'ananicy-cpp'}
	assert available['lib32-glibc'].repository == 'multilib'
	assert available['ananicy-cpp'].version == '1.1.1-3'


def test_duplicate_name_resolves_to_first_repo(monkeypatch: pytest.MonkeyPatch) -> None:
	_stub_pacman(monkeypatch, _SL_OUTPUT)

	available = packages.list_available_packages()

	# pacman resolves by conf order, so core wins over the later cachyos entry
	assert available['nano'].repository == 'core'
	assert available['nano'].version == '8.7-1'


def test_repo_order_follows_the_conf(monkeypatch: pytest.MonkeyPatch) -> None:
	_stub_pacman(monkeypatch, _SL_OUTPUT)

	available = packages.list_available_packages()
	repos = list(dict.fromkeys(p.repository for p in available.values()))

	assert repos == ['core', 'extra', 'multilib', 'cachyos']


def test_sync_failure_still_lists_packages(monkeypatch: pytest.MonkeyPatch) -> None:
	def run(args: str, **kwargs: object) -> list[bytes]:
		if args == '-Sy':
			raise OSError('no network')
		return _SL_OUTPUT

	monkeypatch.setattr(Pacman, 'run', staticmethod(run))

	assert 'linux' in packages.list_available_packages()


def test_list_failure_yields_empty(monkeypatch: pytest.MonkeyPatch) -> None:
	def run(args: str, **kwargs: object) -> list[bytes]:
		raise OSError('pacman missing')

	monkeypatch.setattr(Pacman, 'run', staticmethod(run))

	assert packages.list_available_packages() == {}


# --- enable a repo, then see its packages -------------------------------------
#
# The half above stubs `pacman -Sl` outright. These drive the real loop instead:
# PacmanConfig.apply() edits a pacman.conf, and the fake pacman answers from
# whatever sections that file ends up with. A repo that stops reaching the menu
# fails here rather than on someone's install.

_STOCK_CONF = """\
[options]
HoldPkg = pacman glibc
Architecture = auto

[core]
Include = /etc/pacman.d/mirrorlist

[extra]
Include = /etc/pacman.d/mirrorlist

#[multilib]
#Include = /etc/pacman.d/mirrorlist
"""

_FAKE_DB = {
	'core': [('linux', '6.19.1.arch1-1')],
	'extra': [('neovim', '0.12.2-1')],
	'multilib': [('lib32-glibc', '2.43-2')],
	'cachyos': [('ananicy-cpp', '1.1.1-3')],
}


@pytest.fixture
def conf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> LPath:
	# a pacman.conf we own, plus a pacman that reads it the way the real one does
	pacman_conf = LPath(tmp_path / 'pacman.conf')
	pacman_conf.write_text(_STOCK_CONF)
	monkeypatch.setattr(config, 'PACMAN_CONF', pacman_conf)

	def run(args: str, **kwargs: object) -> list[bytes]:
		if args != '-Sl':
			return []

		lines = []
		for repo in re.findall(r'^\[([^\]]+)\]', pacman_conf.read_text(), re.MULTILINE):
			for name, version in _FAKE_DB.get(repo, []):
				lines.append(f'{repo} {name} {version}\n'.encode())

		return lines

	monkeypatch.setattr(Pacman, 'run', staticmethod(run))
	return pacman_conf


def test_enabling_multilib_surfaces_its_packages(conf: LPath) -> None:
	assert 'lib32-glibc' not in packages.list_available_packages()

	pacman = PacmanConfig(None)
	pacman.enable([Repository.Multilib])
	pacman.apply()
	packages.list_available_packages.cache_clear()

	available = packages.list_available_packages()
	assert available['lib32-glibc'].repository == 'multilib'


def test_adding_a_custom_repo_surfaces_its_packages(conf: LPath) -> None:
	assert 'ananicy-cpp' not in packages.list_available_packages()

	pacman = PacmanConfig(None)
	pacman.enable_custom(
		[
			CustomRepository(
				'cachyos',
				'https://mirror.cachyos.org/repo/x86_64/cachyos',
				SignCheck.Required,
				SignOption.TrustedOnly,
			)
		]
	)
	pacman.apply()
	packages.list_available_packages.cache_clear()

	available = packages.list_available_packages()
	assert available['ananicy-cpp'].repository == 'cachyos'
	# appended after the stock repos, so it loses a name clash with core/extra
	repos = list(dict.fromkeys(p.repository for p in available.values()))
	assert repos == ['core', 'extra', 'cachyos']


def test_stale_cache_hides_a_new_repo(conf: LPath) -> None:
	# why global_menu clears the cache on every pass through the pacman menu and
	# not only when the config looks changed: nothing else invalidates this
	packages.list_available_packages()

	pacman = PacmanConfig(None)
	pacman.enable([Repository.Multilib])
	pacman.apply()

	assert 'lib32-glibc' not in packages.list_available_packages()
	packages.list_available_packages.cache_clear()
	assert 'lib32-glibc' in packages.list_available_packages()
