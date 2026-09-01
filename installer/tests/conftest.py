from pathlib import Path

import pytest

from archinstoo.lib.output import logger


@pytest.fixture(autouse=True)
def _isolate_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# tests import archinstoo and call through SysCommand, which appends to
	# logger.directory (install.log, cmd_history.txt, cmd_output.txt). without
	# this every run would write into the real state dir of whoever ran pytest
	monkeypatch.setattr(logger, '_path', tmp_path / 'logs')


@pytest.fixture(scope='session')
def config_fixture() -> Path:
	return Path(__file__).parent / 'data' / 'test_config.json'
