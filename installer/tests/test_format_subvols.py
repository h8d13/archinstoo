# Marking an existing btrfs partition for formatting kept the subvolumes
# scanned from the old filesystem, and create_btrfs_volumes recreated every
# one of them empty after mkfs (snapper snapshots, nested leftovers). The
# mark now clears them, the unmark brings back the scan.
# On btrfs the menu keeps subvolumes and the partition's own mountpoint
# exclusive, as the mount stage resolves them.

from pathlib import Path
from types import SimpleNamespace

from archinstoo.lib.disk.partitioning_menu import PartitioningList
from archinstoo.lib.models.device import (
	FilesystemType,
	ModificationStatus,
	PartitionModification,
	PartitionType,
	SectorSize,
	Size,
	SubvolumeModification,
	Unit,
)

_DEV = Path('/dev/vdb2')
_SEC = SectorSize.default()


def _scanned() -> SimpleNamespace:
	# what the device scan holds for an existing btrfs partition
	return SimpleNamespace(
		path=_DEV,
		type=PartitionType.PRIMARY,
		start=Size(1, Unit.GiB, _SEC),
		length=Size(20, Unit.GiB, _SEC),
		fs_type=FilesystemType.BTRFS,
		partn=2,
		partuuid='p-uuid',
		uuid='fs-uuid',
		flags=[],
		mountpoints=[],
		btrfs_subvol_infos=[
			SimpleNamespace(name=Path('@'), mountpoint=None),
			SimpleNamespace(
				name=Path('@/.snapshots/1/snapshot'), mountpoint=None
			),
			SimpleNamespace(name=Path('@old_leftover'), mountpoint=None),
		],
	)


def _setup() -> tuple[PartitioningList, PartitionModification]:
	info = _scanned()
	menu = PartitioningList.__new__(PartitioningList)
	menu._device = SimpleNamespace(partition_infos=[info])  # type: ignore[assignment]
	menu._using_gpt = True
	part = PartitionModification.from_existing_partition(info)  # type: ignore[arg-type]
	return menu, part


def _names(part: PartitionModification) -> list[str]:
	return [str(s.name) for s in part.btrfs_subvols]


def test_mark_format_drops_scanned_subvols() -> None:
	menu, part = _setup()

	menu._prompt_formatting(part)

	assert part.status == ModificationStatus.MODIFY
	assert part.btrfs_subvols == []


def test_unmark_format_restores_scan() -> None:
	menu, part = _setup()
	scanned = _names(part)

	menu._prompt_formatting(part)
	menu._prompt_formatting(part)

	assert part.status == ModificationStatus.EXIST
	assert _names(part) == scanned


def test_assign_mountpoint_drops_subvols() -> None:
	menu, part = _setup()

	menu._assign_mountpoint(part, Path('/'), [])

	assert part.mountpoint == Path('/')
	assert part.btrfs_subvols == []


def test_subvols_drop_partition_mountpoint() -> None:
	menu, part = _setup()
	menu._assign_mountpoint(part, Path('/'), [])

	menu._set_subvols(part, [SubvolumeModification(Path('@'), Path('/'))])

	assert part.mountpoint is None
	assert _names(part) == ['@']


def test_unmark_after_assign_leaves_no_stale_root() -> None:
	menu, part = _setup()

	menu._prompt_formatting(part)
	menu._assign_mountpoint(part, Path('/'), [])
	menu._prompt_formatting(part)

	# the scan's subvolumes are back, so the partition is not mounted itself
	assert part.btrfs_subvols
	assert part.mountpoint is None
	assert not part.is_root()
