import importlib
import os
from shutil import rmtree

from archinstoo.lib.output import error, info


def _run_script(script: str) -> None:
	try:
		# by importing we automatically run it
		importlib.import_module(f'archinstoo.scripts.{script}')
	except ModuleNotFoundError as e:
		# Only catch if the missing module is the script itself
		if f'archinstoo.scripts.{script}' in str(e):
			error(f'Script: {script} does not exist. Try `--script list` to see your options.')
			raise SystemExit(1)


def clean_cache(root_dir: str) -> None:
	# only clean if running from source (archinstoo dir exists in cwd)
	if not os.path.isdir(os.path.join(root_dir, 'archinstoo')):
		return

	deleted = []

	info('Cleaning up...')
	try:
		for dirpath, dirnames, _ in os.walk(root_dir):
			for dirname in dirnames:
				if dirname.lower() == '__pycache__':
					full_path = os.path.join(dirpath, dirname)
					try:
						rmtree(full_path)
						deleted.append(full_path)
					except Exception as e:
						info(f'Failed to delete {full_path}: {e}')
	except KeyboardInterrupt, PermissionError:
		pass

	if deleted:
		info(f'Done. {len(deleted)} cache folder(s) deleted.')
