# fstab comes from findmnt's tree under the target: UUID-less mounts (API
# mounts, a self-bind) drop out, btrfs keeps subvol= but not subvolid=

import json
from typing import TYPE_CHECKING, Any

import pytest

from archinstoo.lib.disk import fstab
from archinstoo.lib.exceptions import RequirementError

if TYPE_CHECKING:
	from pathlib import Path


class _Out:
	def __init__(self, data: dict[str, Any]) -> None:
		self._data = data

	def decode(self) -> str:
		return json.dumps(self._data)


def _fs(
	target: str,
	fstype: str,
	options: str,
	uuid: str | None,
	children: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
	fs: dict[str, Any] = {
		'target': target,
		'source': f'/dev/{fstype}',
		'fstype': fstype,
		'options': options,
		'uuid': uuid,
	}
	if children:
		fs['children'] = children
	return fs


TREE = {
	'filesystems': [
		_fs(
			'/mnt',
			'btrfs',
			'rw,relatime,subvolid=256,subvol=/@',
			'root-uuid',
			[
				_fs('/mnt/proc', 'proc', 'rw', None),
				_fs(
					'/mnt/home',
					'btrfs',
					'rw,subvolid=257,subvol=/@home',
					'root-uuid',
				),
				_fs('/mnt/boot', 'vfat', 'rw,fmask=0022', 'ESP-UUID'),
			],
		),
	],
}


def _write(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tree: dict[str, Any]
) -> list[str]:
	monkeypatch.setattr(fstab, 'SysCommand', lambda _cmd: _Out(tree))
	(tmp_path / 'etc').mkdir()
	fstab.write_fstab(tmp_path, ['/swapfile\tnone\tswap\tdefaults\t0\t0'])
	return [
		line
		for line in (tmp_path / 'etc/fstab').read_text().splitlines()
		if line and not line.startswith('#')
	]


def test_mounts_in_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	tree = json.loads(json.dumps(TREE).replace('/mnt', str(tmp_path)))
	assert _write(monkeypatch, tmp_path, tree) == [
		'UUID=root-uuid\t/\tbtrfs\trw,relatime,subvol=/@\t0\t0',
		'UUID=root-uuid\t/home\tbtrfs\trw,subvol=/@home\t0\t0',
		'UUID=ESP-UUID\t/boot\tvfat\trw,fmask=0022\t0\t2',
		'/swapfile\tnone\tswap\tdefaults\t0\t0',
	]


def test_no_root_mounted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	tree = {'filesystems': [_fs(str(tmp_path), 'tmpfs', 'rw', None)]}
	with pytest.raises(RequirementError, match='No root filesystem'):
		_write(monkeypatch, tmp_path, tree)


def test_stacked_mount_hidden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# the bootstrap bound the host's bare /mnt (its root fs) and the target
	# mounted on top: the host's btrfs landed in fstab as / and the install
	# waited on it at boot
	target = str(tmp_path)
	tree = {
		'filesystems': [
			_fs(
				target,
				'btrfs',
				'rw,subvol=/root',
				'host-uuid',
				[_fs(target, 'ext4', 'rw,relatime', 'root-uuid')],
			),
		],
	}
	assert _write(monkeypatch, tmp_path, tree) == [
		'UUID=root-uuid\t/\text4\trw,relatime\t0\t1',
		'/swapfile\tnone\tswap\tdefaults\t0\t0',
	]
