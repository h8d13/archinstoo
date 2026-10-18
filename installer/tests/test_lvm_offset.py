# volumes sized off the PVs ask for a little more than the VG holds
# (metadata): the largest one gives that back, rounded to a 4 MiB extent.
# A hand-written config leaving room in the VG keeps its sizes as asked:
# Size.__sub__ is abs(), so a 40 GiB root in a 61 GiB VG used to lose 21 GiB

from archinstoo.lib.disk.filesystem import lvm_overcommit_offset
from archinstoo.lib.models.device import SectorSize, Size, Unit

SECTOR = SectorSize.default()


def test_overcommit_trimmed_to_extent() -> None:
	desired = Size(61, Unit.GiB, SECTOR)
	avail = Size(61 * 1024 - 3, Unit.MiB, SECTOR)

	assert lvm_overcommit_offset(desired, avail) == Size(4, Unit.MiB, SECTOR)


def test_room_in_vg_keeps_sizes() -> None:
	assert lvm_overcommit_offset(Size(40, Unit.GiB, SECTOR), Size(61, Unit.GiB, SECTOR)) is None


def test_exact_fit_keeps_sizes() -> None:
	size = Size(61, Unit.GiB, SECTOR)

	assert lvm_overcommit_offset(size, size) is None
