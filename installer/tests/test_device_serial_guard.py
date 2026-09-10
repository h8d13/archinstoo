# A saved config names its disk by path. After a disk swap that path is a
# different disk, so the serial travels with the config and is checked on load.
# https://github.com/archlinux/archinstall/issues/2488

from pathlib import Path
from typing import Any

import pytest

from archinstoo.lib.models import device as dev_model
from archinstoo.lib.models.device import BDevice, DiskLayoutConfiguration, SectorSize, Size, Unit, _DeviceInfo


def _stub_device(path: Path, serial: str | None) -> BDevice:
	sector_size = SectorSize.default()
	info = _DeviceInfo(
		model='stub',
		path=path,
		type='gpt',
		total_size=Size(512, Unit.GiB, sector_size),
		free_space_regions=[],
		sector_size=sector_size,
		read_only=False,
		dirty=False,
		serial=serial,
	)
	return BDevice(disk=None, device_info=info, partition_infos=[])  # type: ignore[arg-type]


class _Handler:
	def __init__(self, serial: str | None) -> None:
		self.serial = serial

	def get_device(self, path: Path) -> BDevice:
		return _stub_device(path, self.serial)


def _config(saved_serial: str | None) -> dict[str, Any]:
	entry: dict[str, Any] = {'device': '/dev/vda', 'wipe': True, 'partitions': []}
	if saved_serial:
		entry['serial'] = saved_serial
	return {'config_type': 'default-layout', 'device_modifications': [entry]}


def test_serial_mismatch_refuses() -> None:
	with pytest.raises(ValueError, match='saved for DISK-AAA'):
		DiskLayoutConfiguration.parse_arg(_config('DISK-AAA'), _Handler('DISK-BBB'))  # type: ignore[arg-type]


def test_serial_match_loads() -> None:
	cfg = DiskLayoutConfiguration.parse_arg(_config('DISK-AAA'), _Handler('DISK-AAA'))  # type: ignore[arg-type]
	assert cfg is not None
	assert cfg.device_modifications[0].device.device_info.path == Path('/dev/vda')


@pytest.mark.parametrize(('saved', 'live'), [(None, 'DISK-AAA'), (None, None)])
def test_missing_serial_skips_check(saved: str | None, live: str | None) -> None:
	cfg = DiskLayoutConfiguration.parse_arg(_config(saved), _Handler(live))  # type: ignore[arg-type]
	assert cfg is not None
	assert len(cfg.device_modifications) == 1


def test_saved_serial_but_unknown_disk_refuses() -> None:
	# the saved serial means this exact disk: a serial-less one at that path is not it
	with pytest.raises(ValueError, match='unknown'):
		DiskLayoutConfiguration.parse_arg(_config('DISK-AAA'), _Handler(None))  # type: ignore[arg-type]


def test_json_carries_serial() -> None:
	mod = dev_model.DeviceModification(_stub_device(Path('/dev/vda'), 'DISK-AAA'), wipe=True)
	assert mod.json().get('serial') == 'DISK-AAA'
	assert 'serial' not in dev_model.DeviceModification(_stub_device(Path('/dev/vda'), None), wipe=True).json()
