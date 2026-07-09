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
		# distro ID from os-release; stdlib parse handles quoting and the
		# /usr/lib/os-release fallback (no systemd needed, plain file read)
		try:
			return platform.freedesktop_os_release().get('ID', '')
		except OSError:
			return ''

	@staticmethod
	def running_from_arch() -> bool:
		# distinguishes an Arch host/ISO from a foreign host (Debian, Alpine, ...)
		return Os.running_from_who() == 'arch'

	@staticmethod
	def running_from_foreign() -> bool:
		# installed non-Arch host (not the ISO, not an Arch install)
		return Os.running_from_host() and not Os.running_from_arch()

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
	os.execv(sys.executable, [sys.executable, '-m', 'archinstoo'] + sys.argv[1:])  # noqa: S606 - explicit re-exec of current interpreter


def is_root() -> bool:
	return os.getuid() == 0


def kernel_info() -> str:
	return f'{platform.release()} built {platform.version()}'
