# A config keeps existing partitions by dev_path, but their ids (partn,
# PARTUUID, fs UUID) are live disk state that json() never saves. Parsed
# without them, the bootloader wrote root=UUID=None for an existing root:
# a manual layout reusing partitions, or a saved one replayed. They now come
# from the device scan.

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from archinstoo.lib.models.device import DiskLayoutConfiguration

_SIZE = {'value': 1, 'unit': 'GiB', 'sector_size': {'value': 512, 'unit': 'B'}}


def _partition(status: str, dev_path: str | None) -> dict[str, Any]:
	return {
		'obj_id': f'{status}-{dev_path}',
		'status': status,
		'type': 'primary',
		'start': _SIZE,
		'size': _SIZE,
		'fs_type': 'btrfs',
		'dev_path': dev_path,
		'btrfs': [{'name': '@arch', 'mountpoint': '/'}],
	}


class _Handler:
	def get_device(self, path: Path) -> SimpleNamespace:
		live = SimpleNamespace(
			path=Path('/dev/vdb2'),
			partn=2,
			partuuid='live-partuuid',
			uuid='live-uuid',
		)
		return SimpleNamespace(
			device_info=SimpleNamespace(path=path, serial=None),
			partition_infos=[live],
		)


def _parse(*partitions: dict[str, Any]) -> list[Any]:
	config = {
		'config_type': 'manual-partitioning',
		'device_modifications': [
			{
				'device': '/dev/vdb',
				'wipe': False,
				'partitions': list(partitions),
			}
		],
	}
	parsed = DiskLayoutConfiguration.parse_arg(config, _Handler())  # type: ignore[arg-type]
	assert parsed is not None
	return parsed.device_modifications[0].partitions


def test_existing_partition_takes_live_ids() -> None:
	(part,) = _parse(_partition('existing', '/dev/vdb2'))

	assert (part.partn, part.partuuid, part.uuid) == (
		2,
		'live-partuuid',
		'live-uuid',
	)
