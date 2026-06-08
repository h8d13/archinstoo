# Count packages that would be installed from a saved config.
#
# Resolves the full dependency tree via pactree (pacman-contrib).
# Usage: archinstoo --script count path/to/user_configuration.json

import argparse
import json
from pathlib import Path

from archinstoo.scripts._resolve import collect, resolve_deps


def count() -> None:
	parser = argparse.ArgumentParser(
		prog='python -m archinstoo --script count',
		description='Count packages from a saved config (resolves deps)',
	)
	parser.add_argument('config', type=str, help='Path to user_configuration.json')
	parser.add_argument('--why', metavar='PKG', help='Show which explicit packages pull in PKG and the dep chain')

	args = parser.parse_args()

	with Path(args.config).open() as f:
		config = json.load(f)

	explicit = collect(config)

	print(f'\nExplicit packages/meta/groups: {len(explicit)}')
	print('Resolving dependencies...')

	resolved, roots = resolve_deps(explicit, target=args.why)

	print(f'\nTotal packages (with deps): {len(resolved)}')

	if args.why:
		if not roots:
			print(f"\n'{args.why}' is not pulled in by this config.")
		else:
			print(f"\n'{args.why}' is pulled in by {len(roots)} explicit package(s):")
			for root in sorted(roots):
				print(f'  {root}')


count()
