"""CF Testfile"""

import argparse

from archinstall.lib.models.device import SectorSize, Size, Unit


def size() -> None:
	unit_choices = [u.name for u in Unit]

	parser = argparse.ArgumentParser(
		prog='python -m archinstall --script size',
		description='Convert between storage size units',
	)
	parser.add_argument('value', type=int, help='Size value to convert')
	parser.add_argument('unit', choices=unit_choices, help='Source unit')
	parser.add_argument('--sector-size', type=int, default=512, help='Sector size in bytes')

	mode = parser.add_mutually_exclusive_group()

	mode.add_argument('--to', choices=unit_choices)
	mode.add_argument('--highest', action='store_true')

	args = parser.parse_args()

	sector = SectorSize(args.sector_size, Unit.B)
	src_unit = Unit[args.unit]
	sz = Size(args.value, src_unit, sector)

	if args.to:
		target_unit = Unit[args.to]
		converted = sz.convert(target_unit, sector)
		print(converted.format_size(target_unit))
	elif args.highest:
		print(sz.format_highest())
	else:
		sectors = sz.convert(Unit.sectors, sector)
		print(f'sectors: {sectors.value}')


size()
