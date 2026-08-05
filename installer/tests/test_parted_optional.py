# pyparted is only needed for disk operations. Scripts that never touch
# disk state (NO_DISK_SCRIPTS) must import their whole module chain without
# it, so models/device.py inlines the libparted PED_PARTITION_* constants and
# disk/device_handler.py treats the parted import as optional.
#
# Two guards:
#   - drift:  inlined constants still match the real pyparted values
#   - import: every no-disk script's module chain imports with parted blocked,
#             and DeviceHandler() fails with a clear RequirementError

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from archinstoo import NO_DISK_SCRIPTS

_PKG_ROOT = Path(__file__).parent.parent
_SCRIPTS = _PKG_ROOT / 'archinstoo' / 'scripts'

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

# the scripts call themselves at module level (`live()`), so importing one
# would run an install; replay its top-level imports instead, then the same
# dummy-disk Installer construction they perform (must not build a
# DeviceHandler, which would scan disks through parted)
_DUMMY_INSTALLER = """
from pathlib import Path
from archinstoo.lib.installer import Installer
from archinstoo.lib.models.device import DiskLayoutConfiguration, DiskLayoutType

disk_config = DiskLayoutConfiguration(
	config_type=DiskLayoutType.Pre_mount,
	device_modifications=[],
	mountpoint=Path('/'),
)
Installer(Path('/'), disk_config, kernels=[])
"""


def _script_chain(name: str) -> str:
	# top-level imports only: nested ones belong to codepaths the script
	# reaches at runtime, not to what it needs present to load
	tree = ast.parse((_SCRIPTS / f'{name}.py').read_text())
	imports = [ast.unparse(n) for n in tree.body if isinstance(n, ast.Import | ast.ImportFrom)]
	return '\n'.join(imports) + '\n' + _DUMMY_INSTALLER


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


@pytest.mark.parametrize('script', sorted(NO_DISK_SCRIPTS), ids=str)
def test_no_disk_chain_imports_without_parted(script: str) -> None:
	assert (_SCRIPTS / f'{script}.py').is_file(), f'NO_DISK_SCRIPTS names {script!r}, which has no script module'
	_run_isolated(_BLOCK_PARTED + _script_chain(script))


def test_no_disk_bootstrap_skips_disk_deps() -> None:
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
