# Estimate the installed size of the target system from a saved config.
#
# Reuses the count script's package resolution, then sums each package's
# download and install size from the sync database via expac (pacman-contrib).
# Usage: archinstoo --script size path/to/user_configuration.json

import argparse
import json
import sys
from pathlib import Path

from archinstoo.lib.exceptions import RequirementError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.models.device import SectorSize, Size, Unit
from archinstoo.scripts._resolve import _requirements, collect, resolve_deps

# Binary, disk-relevant units only; the full Unit enum goes up to yottabytes.
_UNIT_CHOICES = ('B', 'KiB', 'MiB', 'GiB', 'TiB')


def _fmt(sz: Size, unit: Unit | None, sector: SectorSize) -> str:
	# Pin to a fixed unit if requested (the old converter behavior), else the highest readable unit.
	if unit is None:
		return sz.format_highest()
	return sz.format_size(unit, sector)


def package_sizes(pkgs: set[str]) -> tuple[int, int, list[tuple[str, int, int]], list[str]]:
	# Query download (%k, compressed) and install (%m, uncompressed) size in bytes
	# per package from the sync DB via expac. Returns:
	#   (total_download, total_install, [(name, download, install)] largest-first, missing)
	found: dict[str, tuple[int, int]] = {}

	output = SysCommand("expac -S '%k:%m:%n' " + ' '.join(sorted(pkgs)))
	for line in output:
		parts = line.decode().rstrip().split(':', 2)
		if len(parts) != 3:
			continue
		dl_str, inst_str, name = parts
		try:
			found[name] = (int(dl_str), int(inst_str))
		except ValueError:
			continue

	missing = sorted(pkgs - found.keys())
	largest = sorted(found.items(), key=lambda kv: kv[1][1], reverse=True)
	total_dl = sum(dl for dl, _ in found.values())
	total_inst = sum(inst for _, inst in found.values())
	return total_dl, total_inst, [(name, dl, inst) for name, (dl, inst) in largest], missing


def size() -> None:
	parser = argparse.ArgumentParser(
		prog='python -m archinstoo --script size',
		description='Estimate the installed size of the target system from a saved config',
		suggest_on_error=True,
	)
	parser.add_argument('config', type=str, help='Path to user_configuration.json')
	parser.add_argument('--top', type=int, default=10, help='Show the N largest packages (0 to hide)')
	parser.add_argument('--unit', choices=_UNIT_CHOICES, help='Pin output to a fixed unit (default: highest readable)')

	args = parser.parse_args()
	unit = Unit[args.unit] if args.unit else None

	with Path(args.config).open() as f:
		config = json.load(f)

	if not _requirements('expac'):
		sys.exit('error: expac not found; install pacman-contrib')

	explicit = collect(config)

	print(f'\nExplicit packages/meta/groups: {len(explicit)}')
	print('Resolving dependencies...')

	try:
		resolved, _ = resolve_deps(explicit)
	except RequirementError as e:
		sys.exit(f'error: {e}')

	print(f'Total packages (with deps): {len(resolved)}')
	print('Querying sizes...')

	total_dl, total_inst, largest, missing = package_sizes(resolved)

	sector = SectorSize(512, Unit.B)
	download = Size(total_dl, Unit.B, sector)
	installed = Size(total_inst, Unit.B, sector)

	print(f'\nDownload:  {_fmt(download, unit, sector)}  (compressed packages to fetch)')
	print(f'Installed: {_fmt(installed, unit, sector)}  (uncompressed on disk)')
	print('  estimate: excludes filesystem overhead, hardlink dedup, and later log/cache/user growth')

	if missing:
		print(f'\n{len(missing)} package(s) not in sync DB (AUR/renamed/virtual), excluded from estimate:')
		print('  ' + ', '.join(missing))

	if args.top > 0 and largest:
		shown = min(args.top, len(largest))
		print(f'\nLargest {shown} packages (installed):')
		for name, _dl, inst in largest[:shown]:
			pkg_size = Size(inst, Unit.B, sector)
			print(f'  {_fmt(pkg_size, unit, sector):>12}  {name}')


size()
