import pytest

from archinstoo.lib.pacman import Pacman
from archinstoo.lib.pm import packages

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
