# the dnf choices reach both the install (setopt on every strap) and the
# installed system (its dnf.conf), and the kernel never takes weak deps

from pathlib import Path

import pytest

from archinstoo.lib.models.dnf import DnfConfiguration
from archinstoo.lib.pm import dnf
from archinstoo.lib.pm.dnf import Dnf


def _strap_argv(monkeypatch: pytest.MonkeyPatch, config: DnfConfiguration, **kw: bool) -> list[str]:
	calls: list[list[str]] = []
	monkeypatch.setattr(dnf, 'mount_api', lambda target: None)
	monkeypatch.setattr(Dnf, 'run', staticmethod(lambda args, **_: calls.append(args)))
	Dnf(Path('/'), config).strap(['kernel'], **kw)
	return calls[0]


def test_config_setopts_reach_the_strap(monkeypatch: pytest.MonkeyPatch) -> None:
	argv = _strap_argv(monkeypatch, DnfConfiguration(install_weak_deps=True, max_parallel_downloads=10))

	assert '--setopt=install_weak_deps=True' in argv
	assert '--setopt=max_parallel_downloads=10' in argv
	assert argv[-1] == 'kernel'


@pytest.mark.parametrize(('configured', 'override'), [(True, False), (False, True)])
def test_strap_override_comes_after_the_config(monkeypatch: pytest.MonkeyPatch, configured: bool, override: bool) -> None:
	# dnf takes the last --setopt for a key: the base forces weak deps on,
	# the kernel off, whatever the config says
	argv = _strap_argv(monkeypatch, DnfConfiguration(install_weak_deps=configured), weak_deps=override)
	weak = [a for a in argv if a.startswith('--setopt=install_weak_deps=')]

	assert weak[-1] == f'--setopt=install_weak_deps={override}'


def test_write_conf_rewrites_in_place(tmp_path: Path) -> None:
	conf = tmp_path / 'etc/dnf/dnf.conf'
	conf.parent.mkdir(parents=True)
	conf.write_text('# see man dnf.conf\n[main]\ninstall_weak_deps=True\nkeepcache=1\n')

	Dnf(tmp_path, DnfConfiguration(install_weak_deps=False, max_parallel_downloads=5)).write_conf()

	assert conf.read_text() == '# see man dnf.conf\n[main]\nmax_parallel_downloads=5\ninstall_weak_deps=False\nkeepcache=1\n'


def test_write_conf_creates_main(tmp_path: Path) -> None:
	Dnf(tmp_path, DnfConfiguration()).write_conf()

	assert (tmp_path / 'etc/dnf/dnf.conf').read_text() == '[main]\ninstall_weak_deps=True\n'


@pytest.mark.parametrize('config', [DnfConfiguration(), DnfConfiguration(install_weak_deps=False, max_parallel_downloads=20)])
def test_round_trip(config: DnfConfiguration) -> None:
	assert DnfConfiguration.parse_arg(config.json()) == config


def test_parallel_downloads_out_of_range() -> None:
	with pytest.raises(ValueError, match='1-20'):
		DnfConfiguration.parse_arg({'max_parallel_downloads': 50})
