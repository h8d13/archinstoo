import json
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.args import ArchConfigHandler
from archinstoo.lib.configuration import ConfigStore

if TYPE_CHECKING:
	import pytest


def test_user_config_roundtrip(
	monkeypatch: pytest.MonkeyPatch,
	config_fixture: Path,
) -> None:
	monkeypatch.setattr('sys.argv', ['archinstoo', '--config', str(config_fixture)])

	handler = ArchConfigHandler()
	arch_config = handler.config

	store = ConfigStore(arch_config)

	test_out_file = Path('/tmp/') / ConfigStore._USER_CONFIG_FILENAME
	monkeypatch.setattr(ConfigStore, '_saved_config_path', classmethod(lambda cls: test_out_file))

	store.save()

	result = json.loads(test_out_file.read_text())
	expected = json.loads(config_fixture.read_text())

	# the parsed config will check if the given device exists otherwise
	# it will ignore the modification; as this test will run on various local systems
	# and the CI pipeline there's no good way specify a real device so we'll simply
	# copy the expected result to the actual result
	result['disk_config']['config_type'] = expected['disk_config']['config_type']
	result['disk_config']['device_modifications'] = expected['disk_config']['device_modifications']

	assert json.dumps(
		result['pacman_config'],
		sort_keys=True,
	) == json.dumps(
		expected['pacman_config'],
		sort_keys=True,
	)
