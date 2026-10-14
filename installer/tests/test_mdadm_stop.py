# a live system assembles arrays from leftover members; wiping a disk has
# to stop each array holding one of its nodes, once, and nothing else

from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.disk import mdadm

if TYPE_CHECKING:
	import pytest


def test_stops_each_holding_array_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# sysfs nests a disk's partitions under it: vda/vda2/holders/md127
	for node, holders in {'vda': [], 'vda/vda1': ['dm-0'], 'vda/vda2': ['md127'], 'vda/vda3': ['md127'], 'vdb/vdb1': ['md0']}.items():
		(tmp_path / node / 'holders').mkdir(parents=True)
		for h in holders:
			(tmp_path / node / 'holders' / h).touch()
	monkeypatch.setattr(mdadm, 'SYS_BLOCK', tmp_path)
	ran: list[list[str]] = []
	monkeypatch.setattr(mdadm, 'SysCommand', ran.append)

	mdadm.stop_arrays_on(Path('/dev/vda'))

	assert ran == [['mdadm', '--stop', '/dev/md127']]
