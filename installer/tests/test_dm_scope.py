# partition() tears down device-mapper nodes before wiping signatures. It
# used to remove every mapper `dmsetup ls` returned, including the host's
# own root LUKS when installing to a second disk. The scope now comes from
# sysfs slaves, so build a fake /sys/block and check what gets selected.

from pathlib import Path

from archinstoo.lib.disk.device_handler import DeviceHandler


def _mapper(sysfs: Path, node: str, name: str, *slaves: str) -> None:
	(sysfs / node / 'dm').mkdir(parents=True)
	(sysfs / node / 'dm' / 'name').write_text(name + '\n')
	for slave in slaves:
		(sysfs / node / 'slaves' / slave).mkdir(parents=True)


def _fake_sysfs(tmp_path: Path) -> Path:
	sysfs = tmp_path / 'block'
	for disk, parts in (
		('vda', ('vda1', 'vda2')),
		('sdb', ('sdb1',)),
		('sda', ('sda1',)),
	):
		for part in parts:
			(sysfs / disk / part).mkdir(parents=True)
	# host root: LUKS on sdb1
	_mapper(sysfs, 'dm-0', 'cryptroot', 'sdb1')
	# target: LUKS on vda2 with an LV stacked on it
	_mapper(sysfs, 'dm-1', 'target-luks', 'vda2')
	_mapper(sysfs, 'dm-2', 'vg-lv', 'dm-1')
	# unrelated: loop-backed mapper
	_mapper(sysfs, 'dm-3', 'loopmap', 'loop0')
	# whole-disk mapper, no partition in between
	_mapper(sysfs, 'dm-4', 'sda-whole', 'sda')
	return sysfs


def test_only_target_mappers_selected(tmp_path: Path) -> None:
	sysfs = _fake_sysfs(tmp_path)
	assert DeviceHandler.dm_names_on_device(Path('/dev/vda'), sysfs) == [
		'vg-lv',
		'target-luks',
	]


def test_host_mapper_stays_when_target_is_other_disk(tmp_path: Path) -> None:
	sysfs = _fake_sysfs(tmp_path)
	assert DeviceHandler.dm_names_on_device(Path('/dev/sdb'), sysfs) == [
		'cryptroot'
	]


def test_whole_disk_mapper_matches(tmp_path: Path) -> None:
	sysfs = _fake_sysfs(tmp_path)
	assert DeviceHandler.dm_names_on_device(Path('/dev/sda'), sysfs) == [
		'sda-whole'
	]


def test_disk_without_mappers_selects_nothing(tmp_path: Path) -> None:
	sysfs = _fake_sysfs(tmp_path)
	assert DeviceHandler.dm_names_on_device(Path('/dev/sdc'), sysfs) == []


# pvs as lvm prints it: VG on a target partition, VG on the target's LUKS
# mapper (LVM on LUKS, missed by the old /dev/vda prefix match), the host's
# VG on its own LUKS, an orphan PV, and a lookalike disk name
_PVS = """\
  tvg   /dev/vda1
  cryptvg /dev/mapper/target-luks
  hostvg /dev/mapper/cryptroot
        /dev/vda2
  othervg /dev/vdaa1
"""


def test_vgs_on_target_partition_and_mapper(tmp_path: Path) -> None:
	sysfs = _fake_sysfs(tmp_path)
	assert DeviceHandler.vgs_on_device(_PVS, Path('/dev/vda'), sysfs) == [
		'tvg',
		'cryptvg',
	]


def test_vgs_leave_host_alone(tmp_path: Path) -> None:
	sysfs = _fake_sysfs(tmp_path)
	assert DeviceHandler.vgs_on_device(_PVS, Path('/dev/sdb'), sysfs) == ['hostvg']
	assert DeviceHandler.vgs_on_device(_PVS, Path('/dev/sdc'), sysfs) == []
