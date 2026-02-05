import argparse

# Example usage
#   archinstoo --script mirror -h
#   archinstoo --script mirror -l
#   archinstoo --script mirror France
from archinstoo.lib.pm.mirrors import MirrorListHandler

parser = argparse.ArgumentParser(
	prog='python -m archinstoo --script mirror',
	description='Test mirror speed sorting',
)
parser.add_argument('region', nargs='?', default='Germany', help='Region to test (default: Germany)')
parser.add_argument('--list', '-l', action='store_true', help='List available regions')
args = parser.parse_args()

handler = MirrorListHandler()
handler.load_mirrors()
regions = handler.get_mirror_regions()

if args.list:
	print('Available regions:')
	for r in regions:
		print(f'  {r.name}')
	raise SystemExit(0)

region_name = args.region
if region_name not in [r.name for r in regions]:
	print(f'Region "{region_name}" not found. Use --list to see available regions.')
	raise SystemExit(1)

mirrors = handler.get_status_by_region(region_name, speed_sort=True)

print(f'\nTop 3 mirrors for {region_name}:')
for m in mirrors[:3]:
	print(f'  {m.speed / 1024 / 1024:.1f} MiB/s - {m.url}')
