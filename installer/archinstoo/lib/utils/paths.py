from pathlib import Path
from shutil import which

from archinstoo.lib.exceptions import RequirementError


# to avoid using shutil.which everywhere
def locate_binary(name: str) -> str:
	if path := which(name):
		return path
	raise RequirementError(f'Binary {name} does not exist.')


# where a package's own data sits under its prefix: share/ on most distros,
# lib/ on fedora, which keeps kbd keymaps and fonts in /usr/lib/kbd
_DATA_DIRS = ('share', 'lib')


def data_paths(anchor: str, *relative: str) -> list[Path]:
	# Data a package ships next to its binaries. /usr on an FHS host, plus the
	# prefix the anchor binary resolves into, which is the only root a store
	# based distro has (NixOS keeps no /usr/share whatsoever). Callers get the
	# candidates in preference order and pick the ones that exist.
	roots = [Path('/usr')]
	if binary := which(anchor):
		roots.append(Path(binary).resolve().parent.parent)

	return [
		root / data / rel
		for root in roots
		for data in _DATA_DIRS
		for rel in relative
	]
