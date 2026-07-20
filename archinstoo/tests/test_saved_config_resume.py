# The saved config written for "resume from saved" goes through jsonify(),
# which drops None values. Any partition without a mountpoint (swap, LVM PV,
# raw) therefore comes back with the key absent, so the resume parse must
# presence-check instead of indexing.

import json
from pathlib import Path
from typing import Any

from archinstoo.lib.general import jsonify
from archinstoo.lib.models.device import (
	BDevice,
	DiskLayoutConfiguration,
	PartitionTable,
	SectorSize,
	Size,
	Unit,
	_DeviceInfo,
)


class _StubDeviceHandler:
	# stands in for a real disk scan: parse_arg only needs a device lookup
	# and the default partition table

	def __init__(self, device: BDevice) -> None:
		self._device = device

	@property
	def partition_table(self) -> PartitionTable:
		return PartitionTable.GPT

	def get_device(self, path: Path) -> BDevice | None:
		return self._device if path == self._device.device_info.path else None


def _stub_device(path: Path) -> BDevice:
	sector_size = SectorSize.default()
	device_info = _DeviceInfo(
		model='stub',
		path=path,
		type='gpt',
		total_size=Size(512, Unit.GiB, sector_size),
		free_space_regions=[],
		sector_size=sector_size,
		read_only=False,
		dirty=False,
	)

	return BDevice(disk=None, device_info=device_info, partition_infos=[])


def _saved_disk_config(config_fixture: Path) -> dict[str, Any]:
	disk_config = json.loads(config_fixture.read_text())['disk_config']

	# a partition with no mountpoint is what triggers the dropped key
	disk_config['device_modifications'][0]['partitions'][2]['mountpoint'] = None

	saved: dict[str, Any] = jsonify(disk_config)
	return saved


def test_resume_parses_partition_without_mountpoint(config_fixture: Path) -> None:
	disk_config = _saved_disk_config(config_fixture)
	partitions = disk_config['device_modifications'][0]['partitions']

	# guard the premise: jsonify dropped the null keys
	assert 'mountpoint' not in partitions[2]
	assert all('dev_path' not in p for p in partitions)

	device_path = Path(disk_config['device_modifications'][0]['device'])
	handler = _StubDeviceHandler(_stub_device(device_path))

	config = DiskLayoutConfiguration.parse_arg(disk_config, device_handler=handler)  # type: ignore[arg-type]

	assert config is not None
	parsed = config.device_modifications[0].partitions
	assert [str(p.mountpoint) if p.mountpoint else None for p in parsed] == ['/boot', '/', None]
	assert all(p.dev_path is None for p in parsed)
