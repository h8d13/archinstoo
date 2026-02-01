import importlib
import os
import sys
from pathlib import Path
from shutil import rmtree, which

from archinstall.lib.exceptions import RequirementError
from archinstall.lib.output import info


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

	@staticmethod
	def running_from_host() -> bool:
		# returns True when not on the ISO
		return not Path('/run/archiso').exists()

	@staticmethod
	def running_from_who() -> str:
		# checks distro name
		if os.path.exists('/etc/os-release'):
			with open('/etc/os-release') as f:
				for line in f:
					if line.startswith('ID='):
						return line.strip().split('=')[1]
		return ''

	@staticmethod
	def running_from_arch() -> bool:
		# confirm its arch host
		return Os.running_from_who() == 'arch'

	# match Os.running_from_who():
	# case 'alpine':
	# do something else

	@staticmethod
	def locate_binary(name: str) -> str:
		if path := which(name):
			return path
		raise RequirementError(f'Binary {name} does not exist.')

	# to avoid using shutil.which everywhere


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


def clean_cache(root_dir: str) -> None:
	deleted = []

	info('Cleaning up...')
	for dirpath, dirnames, _ in os.walk(root_dir):
		for dirname in dirnames:
			if dirname.lower() == '__pycache__':
				full_path = os.path.join(dirpath, dirname)
				try:
					rmtree(full_path)
					deleted.append(full_path)
				except Exception as e:
					info(f'Failed to delete {full_path}: {e}')

	if not deleted:
		info('No cache folders found.')
	else:
		info(f'Done. {len(deleted)} cache folder(s) deleted.')
