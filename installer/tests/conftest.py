from pathlib import Path

import pytest

from archinstoo.lib.output import logger
from archinstoo.lib.utils.host import Host


@pytest.fixture(autouse=True)
def _isolate_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# tests import archinstoo and call through SysCommand, which appends to
	# logger.directory (install.log, cmd_history.txt, cmd_output.txt). without
	# this every run would write into the real state dir of whoever ran pytest
	monkeypatch.setattr(logger, '_path', tmp_path / 'logs')


@pytest.fixture(autouse=True)
def _not_arch_host(monkeypatch: pytest.MonkeyPatch) -> None:
	# an Arch dev box would otherwise run every test in H2T mode (live()
	# copying the real /etc pacman files) where CI does not. Tests that need
	# host mode patch it back on: test_host_workdir, test_prepare
	monkeypatch.setattr(Host, 'running_from_arch_host', staticmethod(lambda: False))


@pytest.fixture(scope='session')
def config_fixture() -> Path:
	return Path(__file__).parent / 'data' / 'test_config.json'


@pytest.fixture(scope='session')
def example_config_fixture() -> Path:
	return Path(__file__).parent.parent / 'examples' / 'config_sample_full.json'
