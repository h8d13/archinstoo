import re
from pathlib import Path

from archinstoo.lib.command import SysCommand
from archinstoo.lib.disk.lsblk import get_lsblk_info
from archinstoo.lib.exceptions import DiskError, SysCallError
from archinstoo.lib.output import debug, info


def mount(
	dev_path: Path | str,
	target_mountpoint: Path,
	mount_fs: str | None = None,
	create_target_mountpoint: bool = True,
	options: list[str] | None = None,
) -> None:
	if create_target_mountpoint and not target_mountpoint.exists():
		target_mountpoint.mkdir(parents=True, exist_ok=True)

	if not target_mountpoint.exists():
		raise ValueError('Target mountpoint does not exist')

	lsblk_info = get_lsblk_info(dev_path)
	if target_mountpoint in lsblk_info.mountpoints:
		info(f'Device already mounted at {target_mountpoint}')
		return

	cmd = ['mount']

	if options:
		cmd.extend(('-o', ','.join(options)))
	if mount_fs:
		cmd.extend(('-t', mount_fs))

	cmd.extend((str(dev_path), str(target_mountpoint)))

	command = ' '.join(cmd)
	debug(f'Mounting {dev_path}: {command}')

	try:
		SysCommand(command)
	except SysCallError as err:
		raise DiskError(
			f'Could not mount {dev_path}: {command}\n{err.message}'
		) from err


def umount(dev_path: Path | str, recursive: bool = False) -> None:
	lsblk_info = get_lsblk_info(dev_path)

	# swap first: a swap file keeps its fs busy, and the lazy fallback
	# below would detach it still active, renamed in /proc/swaps
	for area in swaps_on(Path(dev_path), lsblk_info.mountpoints):
		swapoff(area)

	if not lsblk_info.mountpoints:
		debug(f'{dev_path} has no mountpoints, nothing to unmount')
		return

	debug(
		f'Partition {dev_path} is currently mounted at: '
		f'{[str(m) for m in lsblk_info.mountpoints]}'
	)

	cmd = ['umount']

	if recursive:
		cmd.append('-R')

	for path in lsblk_info.mountpoints:
		debug(f'Unmounting mountpoint: {path}')
		try:
			SysCommand([*cmd, str(path)])
		except SysCallError as e:
			# If busy, try lazy unmount
			if 'busy' in str(e).lower():
				debug(f'Mount busy, trying lazy unmount: {path}')
				lazy_cmd = cmd.copy()
				lazy_cmd.insert(1, '-l')  # Insert -l after 'umount'
				SysCommand([*lazy_cmd, str(path)])
			else:
				raise


def _unescape(field: str) -> str:
	# /proc/swaps octal-escapes whitespace and backslash (space as \040)
	return re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), field)


def active_swaps() -> list[Path]:
	# the kernel's state: lsblk shows a swap device only as [SWAP]
	# (dropped on parse) and a swap file not at all
	lines = Path('/proc/swaps').read_text().splitlines()[1:]
	return [
		Path(_unescape(fields[0])) for line in lines if (fields := line.split())
	]


def swaps_on(dev_path: Path, mountpoints: list[Path]) -> list[Path]:
	# the device itself (/proc/swaps names /dev/dm-N, so resolve a mapper
	# link) or a swap file below one of its mountpoints
	dev = dev_path.resolve()
	return [
		area
		for area in active_swaps()
		if area == dev or any(area.is_relative_to(m) for m in mountpoints)
	]


def swapon(path: Path) -> None:
	# swap is machine-wide: a previous run may have left this area on
	if swaps_on(path, []):
		debug(f'Swap already active on {path}')
		return

	try:
		SysCommand(['swapon', str(path)])
	except SysCallError as err:
		raise DiskError(
			f'Could not enable swap {path}:\n{err.message}'
		) from err


def swapoff(path: Path) -> None:
	debug(f'Disabling swap: {path}')
	try:
		SysCommand(['swapoff', str(path)])
	except SysCallError as err:
		raise DiskError(
			f'Could not disable swap {path}:\n{err.message}'
		) from err
