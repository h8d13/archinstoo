from pathlib import Path

import pytest

from archinstoo.lib.output import logger
from archinstoo.lib.pm import pacman


@pytest.fixture(autouse=True)
def _isolate_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# tests import archinstoo and call through SysCommand, which appends to
	# logger.directory (install.log, cmd_history.txt, cmd_output.txt). without
	# this every run would write into the real state dir of whoever ran pytest
	monkeypatch.setattr(logger, '_path', tmp_path / 'logs')


@pytest.fixture(autouse=True)
def _no_host_workdir(monkeypatch: pytest.MonkeyPatch) -> None:
	# on an Arch dev box every live() would copy the real /etc pacman files;
	# tests point PACMAN_CONF at their own. test_host_workdir covers the copy
	monkeypatch.setattr(pacman, '_host_workdir', lambda: None)


@pytest.fixture(scope='session')
def config_fixture() -> Path:
	return Path(__file__).parent / 'data' / 'test_config.json'


@pytest.fixture(scope='session')
def example_config_fixture() -> Path:
	return Path(__file__).parent.parent / 'examples' / 'config_sample_full.json'
