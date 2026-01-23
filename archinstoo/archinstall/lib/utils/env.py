import importlib
import os
import shutil
import sys
from pathlib import Path


class Os:
	@staticmethod
	def set_env(key: str, value: str) -> None:
		os.environ[key] = value

	@staticmethod
	def get_env(key: str, default: str | None = None) -> str | None:
		return os.environ.get(key, default)

	@staticmethod
	def has_env(key: str) -> bool:
		return key in os.environ


def is_venv() -> bool:
	return sys.prefix != getattr(sys, 'base_prefix', sys.prefix)


def _run_script(script: str) -> None:
	importlib.import_module(f'archinstall.scripts.{script}')


def reload_python() -> None:
	# dirty python trick to reload any changed library modules
	# skip reload during testing to avoid running system archinstall
	if 'pytest' in sys.modules:
		return
	os.execv(sys.executable, [sys.executable, '-m', 'archinstall'] + sys.argv[1:])


def is_root() -> bool:
	return os.getuid() == 0


def running_from_host() -> bool:
	# returns True when not on the ISO
	return not Path('/run/archiso').exists()


def clean_cache(root_dir: str) -> None:
	from ..output import info

	deleted = []

	info('Cleaning up...')
	for dirpath, dirnames, _ in os.walk(root_dir):
		for dirname in dirnames:
			if dirname.lower() == '__pycache__':
				full_path = os.path.join(dirpath, dirname)
				try:
					shutil.rmtree(full_path)
					deleted.append(full_path)
				except Exception as e:
					info(f'Failed to delete {full_path}: {e}')

	if not deleted:
		info('No cache folders found.')
	else:
		info(f'Done. {len(deleted)} cache folder(s) deleted.')
