import json
from pathlib import Path

from pytest import MonkeyPatch

from archinstall.lib.args import ArchConfigHandler
from archinstall.lib.configuration import ConfigurationHandler


def test_user_config_roundtrip(
	monkeypatch: MonkeyPatch,
	config_fixture: Path,
) -> None:
	monkeypatch.setattr('sys.argv', ['archinstall', '--config', str(config_fixture)])

	handler = ArchConfigHandler()
	arch_config = handler.config

	config_output = ConfigurationHandler(arch_config)

	test_out_file = Path('/tmp/') / ConfigurationHandler._USER_CONFIG_FILENAME
	monkeypatch.setattr(ConfigurationHandler, '_saved_config_path', classmethod(lambda cls: test_out_file))

	config_output.save()

	result = json.loads(test_out_file.read_text())
	expected = json.loads(config_fixture.read_text())

	# the parsed config will check if the given device exists otherwise
	# it will ignore the modification; as this test will run on various local systems
	# and the CI pipeline there's no good way specify a real device so we'll simply
	# copy the expected result to the actual result
	result['disk_config']['config_type'] = expected['disk_config']['config_type']
	result['disk_config']['device_modifications'] = expected['disk_config']['device_modifications']

	assert json.dumps(
		result['mirror_config'],
		sort_keys=True,
	) == json.dumps(
		expected['mirror_config'],
		sort_keys=True,
	)
