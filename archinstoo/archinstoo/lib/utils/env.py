import os
import platform
import sys
from pathlib import Path
from shutil import which

from archinstoo.lib.exceptions import RequirementError


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
	def locate_binary(name: str) -> str:
		if path := which(name):
			return path
		raise RequirementError(f'Binary {name} does not exist.')

	# to avoid using shutil.which everywhere


def is_venv() -> bool:
	return sys.prefix != getattr(sys, 'base_prefix', sys.prefix)


def reload_python() -> None:
	# dirty python trick to reload any changed library modules
	# skip reload during testing
	if 'pytest' in sys.modules:
		return
	os.execv(sys.executable, [sys.executable, '-m', 'archinstoo'] + sys.argv[1:])


def is_root() -> bool:
	return os.getuid() == 0


def kernel_info() -> str:
	return f'{platform.release()} built {platform.version()}'
