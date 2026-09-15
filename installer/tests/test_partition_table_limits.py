# MBR entries hold start LBA and length as uint32, so a disk larger than
# 2^32 sectors has a tail no MBR layout can reach.
# https://github.com/archlinux/archinstall/issues/2087

from pathlib import Path

import pytest

from archinstoo.lib.disk.device_handler import DeviceHandler
from archinstoo.lib.disk.partitioning_menu import PartitioningList
from archinstoo.lib.disk.selectors import default_partition_table
from archinstoo.lib.exceptions import DiskError
from archinstoo.lib.models.device import (
	BDevice,
	DeviceModification,
	FilesystemType,
	ModificationStatus,
	PartitionModification,
	PartitionTable,
	PartitionType,
	SectorSize,
	Size,
	Unit,
	_DeviceInfo,
)

S512 = SectorSize(512, Unit.B)
S4K = SectorSize(4096, Unit.B)


class _StubDisk:
	# using_gpt reads the label off the parted disk when nothing is wiped
	def __init__(self, table: PartitionTable) -> None:
		self.type = table.value


def _device(total: Size, sector_size: SectorSize, table: PartitionTable = PartitionTable.GPT) -> BDevice:
	info = _DeviceInfo('stub', Path('/dev/vda'), 'disk', total, [], sector_size, False, False)
	return BDevice(disk=_StubDisk(table), device_info=info, partition_infos=[])  # type: ignore[arg-type]


def _part(start: Size, length: Size) -> PartitionModification:
	return PartitionModification(
		status=ModificationStatus.CREATE,
		type=PartitionType.PRIMARY,
		start=start,
		length=length,
		fs_type=FilesystemType.EXT4,
		mountpoint=Path('/'),
	)


@pytest.mark.parametrize('wipe', [True, False])
def test_partition_rejects_an_unaddressable_mbr_layout(wipe: bool) -> None:
	# both paths: a fresh msdos table, and an existing one being added to
	device = _device(Size(4, Unit.TiB, S512), S512, table=PartitionTable.MBR)
	mod = DeviceModification(
		device=device,
		wipe=wipe,
		partitions=[_part(Size(1, Unit.MiB, S512), Size(3, Unit.TiB, S512))],
		partition_table=PartitionTable.MBR if wipe else None,
	)

	with pytest.raises(DiskError, match='ends past what msdos can address'):
		DeviceHandler._validate_addressable(mod, PartitionTable.MBR)


def test_partition_accepts_the_same_layout_on_gpt() -> None:
	device = _device(Size(4, Unit.TiB, S512), S512)
	mod = DeviceModification(
		device=device,
		wipe=True,
		partitions=[_part(Size(1, Unit.MiB, S512), Size(3, Unit.TiB, S512))],
		partition_table=PartitionTable.GPT,
	)

	DeviceHandler._validate_addressable(mod, PartitionTable.GPT)


def test_uefi_disk_on_an_mbr_label_is_still_checked() -> None:
	# the handler default said GPT, so the ceiling used to be skipped here
	device = _device(Size(4, Unit.TiB, S512), S512, table=PartitionTable.MBR)
	mod = DeviceModification(
		device=device,
		wipe=False,
		partitions=[_part(Size(1, Unit.MiB, S512), Size(3, Unit.TiB, S512))],
	)

	with pytest.raises(DiskError, match='ends past what msdos can address'):
		DeviceHandler._validate_addressable(mod, PartitionTable.GPT)


@pytest.mark.parametrize(
	('total', 'sector_size', 'expected'),
	[
		(Size(64, Unit.GiB, S512), S512, PartitionTable.MBR),
		(Size(4, Unit.TiB, S512), S512, PartitionTable.GPT),
		# the same disk fits inside MBR once the sectors are 4K
		(Size(4, Unit.TiB, S4K), S4K, PartitionTable.MBR),
	],
)
def test_default_table_flips_to_gpt_past_the_mbr_ceiling(
	monkeypatch: pytest.MonkeyPatch,
	total: Size,
	sector_size: SectorSize,
	expected: PartitionTable,
) -> None:
	monkeypatch.setattr('archinstoo.lib.hardware.SysInfo.has_uefi', staticmethod(lambda: False))
	assert default_partition_table(_device(total, sector_size)) == expected


def test_default_table_stays_gpt_on_uefi(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr('archinstoo.lib.hardware.SysInfo.has_uefi', staticmethod(lambda: True))
	assert default_partition_table(_device(Size(64, Unit.GiB, S512), S512)) == PartitionTable.GPT


@pytest.mark.parametrize(
	('table', 'expected'),
	[
		(PartitionTable.MBR, '2 TiB'),
		(PartitionTable.GPT, '4 TiB'),
	],
)
def test_menu_free_space_stops_where_the_table_does(table: PartitionTable, expected: str) -> None:
	# msdos used to offer the whole 4 TiB, failing later at partitioning
	mod = DeviceModification(device=_device(Size(4, Unit.TiB, S512), S512), wipe=True, partition_table=table)
	free = PartitioningList(mod, table).as_segments([])[0].segment
	assert free.end.format_highest() == expected
