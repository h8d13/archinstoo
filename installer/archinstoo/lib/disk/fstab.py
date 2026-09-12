from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import RequirementError, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.output import info

if TYPE_CHECKING:
	from pathlib import Path


def write_fstab(target: Path, extra_entries: list[str], flags: str = '-pU') -> None:
	# genfstab output plus what the install learned that genfstab cannot see (swap files, encrypted swap)
	fstab_path = target / 'etc' / 'fstab'
	info(f'Generating {fstab_path}', step=True)
	try:
		gen_fstab = SysCommand(f'genfstab {flags} -f {target} {target}').output()
	except SysCallError as err:
		raise RequirementError(f'Could not generate fstab, strapping in packages most likely failed (disk out of space?)\n Error: {err}') from err

	with fstab_path.open('ab') as fp:
		fp.write(gen_fstab)

	if not fstab_path.is_file():
		raise RequirementError('Could not create fstab file')

	with fstab_path.open('a') as fp:
		fp.writelines(f'{entry}\n' for entry in extra_entries)
