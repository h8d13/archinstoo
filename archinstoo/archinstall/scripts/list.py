import glob
from pathlib import Path

print('Available options:')

for script in [Path(x) for x in glob.glob(f'{Path(__file__).parent}/*.py')]:
	if script.stem in ['__init__', 'list']:
		continue

	print(f'    {script.stem}')
