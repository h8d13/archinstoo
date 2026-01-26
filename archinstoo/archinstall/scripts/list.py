import glob
from pathlib import Path

from archinstall.lib.args import ROOTLESS_SCRIPTS

print('Available options:')

for script in [Path(x) for x in glob.glob(f'{Path(__file__).parent}/*.py')]:
	if script.stem in ['__init__', 'list']:
		continue

	tag = '' if script.stem in ROOTLESS_SCRIPTS else '  [*] requires root'
	print(f'    {script.stem}{tag}')
