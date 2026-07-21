# pyparted is only needed for disk operations. Scripts that never touch
# disk state (live) must import their whole module chain without it, so
# models/device.py inlines the libparted PED_PARTITION_* constants and
# disk/device_handler.py treats the parted import as optional.
#
# Two guards:
#   - drift:  inlined constants still match the real pyparted values
#   - import: the live-script module chain imports with parted blocked,
#             and DeviceHandler() fails with a clear RequirementError

import subprocess
import sys
from pathlib import Path

import pytest

_PKG_ROOT = Path(__file__).parent.parent

# raising ModuleNotFoundError from find_spec mirrors a missing package
# exactly (sys.modules[name] = None raises plain ImportError instead)
_BLOCK_PARTED = """
import sys

class _BlockParted:
	def find_spec(self, name, path=None, target=None):
		if name in ('parted', '_ped') or name.startswith('parted.'):
			raise ModuleNotFoundError(f'No module named {name!r}')
		return None

sys.meta_path.insert(0, _BlockParted())
"""

# every module scripts/live.py pulls in at import time, then the same
# dummy-disk Installer construction live.py performs (must not build a
# DeviceHandler, which would scan disks through parted)
_LIVE_CHAIN = """
from pathlib import Path

from archinstoo.lib.applications.application_handler import ApplicationHandler
from archinstoo.lib.args import ArchConfig, ArchConfigHandler, Arguments
from archinstoo.lib.authentication.shell import ShellApp
from archinstoo.lib.configuration import ConfigStore
from archinstoo.lib.global_menu import GlobalMenu
from archinstoo.lib.installer import Installer
from archinstoo.lib.models.device import DiskLayoutConfiguration, DiskLayoutType
from archinstoo.lib.network.network_handler import NetworkHandler
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.lib.tui import Tui

disk_config = DiskLayoutConfiguration(
	config_type=DiskLayoutType.Pre_mount,
	device_modifications=[],
	mountpoint=Path('/'),
)
Installer(Path('/'), disk_config, kernels=[])
"""

_HANDLER_GUARD = """
from archinstoo.lib.disk.device_handler import DeviceHandler
from archinstoo.lib.exceptions import RequirementError

try:
	DeviceHandler()
except RequirementError:
	pass
else:
	raise AssertionError('DeviceHandler() must raise RequirementError without pyparted')
"""


def _run_isolated(code: str) -> None:
	result = subprocess.run(  # noqa: S603 - cmd is project-controlled list, not user input
		[sys.executable, '-c', code],
		cwd=_PKG_ROOT,
		capture_output=True,
		text=True,
		check=False,
	)
	assert result.returncode == 0, f'stdout:\n{result.stdout}\nstderr:\n{result.stderr}'


def test_live_chain_imports_without_parted() -> None:
	_run_isolated(_BLOCK_PARTED + _LIVE_CHAIN)


def test_live_bootstrap_skips_disk_deps() -> None:
	# the import guard above is pointless if bootstrap installs parted anyway
	from archinstoo import base_depends, disk_depends

	assert 'python-pyparted' in disk_depends
	assert not set(base_depends) & set(disk_depends)


def test_device_handler_requires_parted() -> None:
	_run_isolated(_BLOCK_PARTED + _HANDLER_GUARD)


def test_ped_constants_match_pyparted() -> None:
	parted = pytest.importorskip('parted')

	from archinstoo.lib.models import device

	assert device._PED_PARTITION_NORMAL == parted.PARTITION_NORMAL
	assert device._PED_PARTITION_BOOT == parted.PARTITION_BOOT
	assert device._PED_PARTITION_SWAP == parted.PARTITION_SWAP
	assert device._PED_PARTITION_BIOS_GRUB == parted.PARTITION_BIOS_GRUB
	assert device._PED_PARTITION_ESP == parted.PARTITION_ESP
	assert device._PED_PARTITION_BLS_BOOT == parted.PARTITION_BLS_BOOT
	assert device._PED_PARTITION_LINUX_HOME == parted.PARTITION_LINUX_HOME
