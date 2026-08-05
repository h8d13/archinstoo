from pathlib import Path

import pytest


@pytest.fixture(scope='session')
def config_fixture() -> Path:
	return Path(__file__).parent / 'data' / 'test_config.json'
