from pathlib import Path

from archinstoo import ROOTLESS_SCRIPTS
from archinstoo.lib.args import DEFAULT_SCRIPT

scripts = [p.stem for p in Path(__file__).parent.glob('*.py') if not p.stem.startswith('_') and p.stem != 'list']

rootless = sorted(s for s in scripts if s in ROOTLESS_SCRIPTS)
root = sorted(s for s in scripts if s not in ROOTLESS_SCRIPTS)

all_scripts = rootless + root
width = max(len(s) for s in all_scripts)

print('Available options:')
print(' 	      [*] requires root')
for name in rootless:
	print(f'    {name}')

for name in root:
	if name == DEFAULT_SCRIPT:
		print(f'    {name:<{width}}  [*] < DEFAULT')
	else:
		print(f'    {name:<{width}}  [*]')
