import glob
from pathlib import Path

from archinstall.lib.args import ROOTLESS_SCRIPTS

scripts = [Path(x).stem for x in glob.glob(f'{Path(__file__).parent}/*.py') if Path(x).stem not in ('__init__', 'list')]

rootless = sorted(s for s in scripts if s in ROOTLESS_SCRIPTS)
root = sorted(s for s in scripts if s not in ROOTLESS_SCRIPTS)

print('Available options:')

for name in rootless:
	print(f'    {name}')

for name in root:
	print(f'    {name}  [*] requires root')
