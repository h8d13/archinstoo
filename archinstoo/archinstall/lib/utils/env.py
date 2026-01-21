import os
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


def running_from_host() -> bool:
	# returns True when not on the ISO
	return not Path('/run/archiso').exists()
