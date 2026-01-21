import sys
from pathlib import Path


def running_from_host() -> bool:
	"""
	Check if running from an installed system.

	Returns True if running from installed system (host mode) for host-to-target install.
	Returns False if /run/archiso exists (ISO mode).
	"""
	return not Path('/run/archiso').exists()


def is_venv() -> bool:
	return sys.prefix != getattr(sys, 'base_prefix', sys.prefix)
