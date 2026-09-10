# umount_all_existing() ran `umount -R /` (then `umount -l /`) when the target
# disk was the one booting the host. https://github.com/archlinux/archinstall/issues/4275

from pathlib import Path
from typing import Any

import pytest

from archinstoo.lib.disk import device_handler as dh
from archinstoo.lib.exceptions import DiskError
from archinstoo.lib.models.device import LsblkInfo


def _node(name: str, mountpoints: list[str], children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
	return {
		'name': name,
		'path': f'/dev/{name}',
		'type': 'part',
		'mountpoints': mountpoints,
		'children': children or [],
	}


# lsblk /dev/vda on the dev VM booted from its own LUKS install
HOST_DISK = _node('vda', [], [_node('vda1', ['/boot']), _node('vda2', [], [_node('root', ['/'])])])
# a data disk the host has mounted but does not run from
DATA_DISK = _node('vdb', [], [_node('vdb1', ['/mnt/data', '/srv'])])


def test_host_mounts_walks_mapper_children() -> None:
	assert dh.host_mounts(LsblkInfo.from_dict(HOST_DISK)) == [Path('/boot'), Path('/')]


def test_host_mounts_ignores_data_disk() -> None:
	assert dh.host_mounts(LsblkInfo.from_dict(DATA_DISK)) == []


def test_umount_all_existing_refuses_host_disk(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(dh, 'get_lsblk_info', lambda path: LsblkInfo.from_dict(HOST_DISK))
	handler = dh.DeviceHandler.__new__(dh.DeviceHandler)
	with pytest.raises(DiskError, match='running system'):
		handler.umount_all_existing(Path('/dev/vda'))
