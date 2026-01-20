"""CF Testfile"""

import argparse

from archinstall.lib.models.device import SectorSize, Size, Unit


def main() -> None:
	unit_choices = [u.name for u in Unit]

	parser = argparse.ArgumentParser()
	parser.add_argument('value', type=int)
	parser.add_argument('unit', choices=unit_choices)
	parser.add_argument('--sector-size', type=int, default=512)

	mode = parser.add_mutually_exclusive_group()

	mode.add_argument('--to', choices=unit_choices)
	mode.add_argument('--highest', action='store_true')

	args = parser.parse_args()

	sector = SectorSize(args.sector_size, Unit.B)
	src_unit = Unit[args.unit]
	size = Size(args.value, src_unit, sector)

	if args.to:
		target_unit = Unit[args.to]
		converted = size.convert(target_unit, sector)
		print(converted.format_size(target_unit))
	elif args.highest:
		print(size.format_highest())
	else:
		sectors = size.convert(Unit.sectors, sector)
		print(f'sectors: {sectors.value}')


if __name__ == '__main__':
	main()
