from pathlib import Path

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.output import debug, info, warn

SYS_BLOCK = Path('/sys/class/block')


def scan_arrays() -> str:
	# one ARRAY line per array assembled on the host. output(), not decode():
	# the command runs on a pty, so every line comes back CRLF, and mdadm reads
	# the stray CR as part of the UUID and drops the whole ARRAY line
	try:
		return SysCommand(['mdadm', '--detail', '--scan']).output().decode('utf-8', errors='backslashreplace')
	except SysCallError as err:
		debug(f'mdadm --detail --scan failed: {err}')
		return ''


def stop_arrays_on(device: Path) -> None:
	# a live system's udev assembles every array it finds members of; while
	# one runs its members stay busy, so wipefs cannot open them and the
	# kernel keeps the old partition table. The kernel's partitions, not the
	# on-disk table: after a failed commit the two disagree
	node = SYS_BLOCK / device.name
	holders = [*node.glob('holders/md*'), *node.glob(f'{device.name}*/holders/md*')]
	arrays = sorted({h.name for h in holders})
	for md in arrays:
		info(f'Stopping md array /dev/{md}')
		SysCommand(['mdadm', '--stop', f'/dev/{md}'])


def array_uuid(dev_path: Path) -> str:
	# mdadm's own UUID notation (colon groups), the one rd.md.uuid= takes
	out = SysCommand(['mdadm', '--detail', '--export', str(dev_path)]).output().decode()
	for line in out.splitlines():
		key, _, value = line.strip().partition('=')
		if key == 'MD_UUID':
			return value
	raise SysCallError(f'No MD_UUID for {dev_path}')


def write_mdadm_conf(target: Path) -> None:
	# udev assembles by metadata alone, but only arrays named here come
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
