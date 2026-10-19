from pathlib import Path

from archinstoo import ROOTLESS_SCRIPTS
from archinstoo.lib.cli import DEFAULT_SCRIPT

here = Path(__file__).parent
# subfolders are namespaces (dev/vm.py runs as dev.vm); anything under a
# _private name (_resolve.py, dev/_vm.py, __pycache__) is a helper, not a script
scripts = [
	'.'.join(rel.with_suffix('').parts)
	for rel in (p.relative_to(here) for p in here.rglob('*.py'))
	if not any(part.startswith('_') for part in rel.parts)
	and rel != Path('list.py')
]

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
