from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.output import debug, info, warn

if TYPE_CHECKING:
	from pathlib import Path


def scan_arrays() -> str:
	# one ARRAY line per array assembled on the host. output(), not decode():
	# the command runs on a pty, so every line comes back CRLF, and mdadm reads
	# the stray CR as part of the UUID and drops the whole ARRAY line
	try:
		return SysCommand(['mdadm', '--detail', '--scan']).output().decode('utf-8', errors='backslashreplace')
	except SysCallError as err:
		debug(f'mdadm --detail --scan failed: {err}')
		return ''


def write_mdadm_conf(target: Path) -> None:
	# mdadm_udev assembles by metadata alone, but only arrays named here come
	# back under their own name; without them the root is /dev/md127. MAILADDR
	# too: `mdadm --monitor` exits 1 when neither it nor PROGRAM is set, and
	# the packaged config leaves both commented, so mdmonitor.service would
	# land the fresh install in a degraded state.
	# Appended, not written: the file is mdadm's own and documents the rest.
	arrays = scan_arrays()

	if not arrays:
		warn('Could not scan md arrays, leaving mdadm.conf alone')
		return

	if not arrays.endswith('\n'):
		arrays += '\n'

	conf_path = target / 'etc' / 'mdadm.conf'
	with conf_path.open('a') as conf:
		conf.write(f'\n{arrays}MAILADDR root\n')

	info(f'Added {len(arrays.splitlines())} array(s) and MAILADDR to {conf_path}')
