import contextlib
from getpass import getpass
from pathlib import Path

from archinstall.lib.args import get_arch_config_handler
from archinstall.lib.disk.device_handler import DeviceHandler
from archinstall.lib.disk.luks import Luks2
from archinstall.lib.disk.utils import get_all_lsblk_info, get_lsblk_by_mountpoint
from archinstall.lib.exceptions import DiskError, SysCallError
from archinstall.lib.general import SysCommand
from archinstall.lib.models.device import FilesystemType, LsblkInfo, Unit
from archinstall.lib.models.users import Password
from archinstall.lib.output import debug, error, info, warn
from archinstall.lib.tui import Tui
from archinstall.lib.tui.curses_menu import SelectMenu
from archinstall.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.lib.tui.result import ResultType
from archinstall.lib.tui.types import Alignment

# Filesystem types that could contain a Linux root
LINUX_FILESYSTEMS = {
	FilesystemType.Ext2,
	FilesystemType.Ext3,
	FilesystemType.Ext4,
	FilesystemType.Btrfs,
	FilesystemType.Xfs,
	FilesystemType.F2fs,
}


def activate_lvm_volumes() -> None:
	"""Activate all LVM volume groups."""
	try:
		SysCommand(['vgchange', '-ay'])
		info('LVM volume groups activated')
	except SysCallError:
		debug('No LVM volume groups found or vgchange not available')


def find_luks_partitions(lsblk_infos: list[LsblkInfo]) -> list[LsblkInfo]:
	"""Find all LUKS encrypted partitions."""
	luks_partitions: list[LsblkInfo] = []

	def _check_partition(lsblk_info: LsblkInfo) -> None:
		if lsblk_info.fstype == FilesystemType.Crypto_luks.value:
			luks_partitions.append(lsblk_info)

		for child in lsblk_info.children:
			_check_partition(child)

	for device in lsblk_infos:
		_check_partition(device)

	return luks_partitions


def find_linux_partitions(lsblk_infos: list[LsblkInfo]) -> list[LsblkInfo]:
	"""
	Looks for ext4, btrfs, xfs filesystems that are not currently mounted.
	"""
	linux_partitions: list[LsblkInfo] = []
	fs_values = {fs.value for fs in LINUX_FILESYSTEMS}

	def _check_partition(lsblk_info: LsblkInfo) -> None:
		# Check if it's a partition or LVM volume with a Linux filesystem
		# Include partitions that are not mounted or mounted elsewhere (not on /mnt or /)
		if lsblk_info.fstype in fs_values and (not lsblk_info.mountpoints or all(str(mp) not in ['/', '/mnt'] for mp in lsblk_info.mountpoints)):
			linux_partitions.append(lsblk_info)

		# Recursively check children (for LVM, etc.)
		for child in lsblk_info.children:
			_check_partition(child)

	for device in lsblk_infos:
		_check_partition(device)

	return linux_partitions


def verify_linux_root(mount_point: Path) -> bool:
	required_paths = [
		mount_point / 'etc',
		mount_point / 'usr',
		mount_point / 'var',
	]

	# Check for required directories
	for path in required_paths:
		if not path.exists():
			return False

	# Check for os-release (standard on most modern Linux distros)
	os_release = mount_point / 'etc' / 'os-release'

	return os_release.exists()


def mount_partition(partition: LsblkInfo, mount_point: Path, handler: DeviceHandler) -> bool:
	try:
		info(f'Mounting {partition.path} to {mount_point}...')
		handler.mount(partition.path, mount_point, create_target_mountpoint=True)
		return True
	except DiskError as e:
		error(f'Failed to mount {partition.path}: {e}')
		return False


def mount_additional_filesystems(mount_point: Path, handler: DeviceHandler) -> None:
	fstab_path = mount_point / 'etc' / 'fstab'

	if not fstab_path.exists():
		warn('No /etc/fstab found, skipping additional mounts')
		return

	info('Reading /etc/fstab to mount additional filesystems...')

	try:
		with open(fstab_path) as f:
			for line in f:
				line = line.strip()

				# Skip comments and empty lines
				if not line or line.startswith('#'):
					continue

				parts = line.split()
				if len(parts) < 3:
					continue

				device, mountpoint, fstype = parts[0], parts[1], parts[2]

				# Skip the root filesystem and special filesystems
				if mountpoint in ['/', 'none', 'swap'] or mountpoint.startswith(('/proc', '/sys', '/dev', '/run')):
					continue

				# Skip swap
				if fstype == 'swap':
					continue

				target_path = mount_point / mountpoint.lstrip('/')

				try:
					handler.mount(Path(device), target_path, create_target_mountpoint=True)
					info(f'Mounted {device} to {target_path}')
				except (DiskError, SysCallError):
					warn(f'Could not mount {device} to {target_path}, skipping...')

	except Exception as e:
		warn(f'Error reading fstab: {e}')


def unmount_all(mount_point: Path) -> None:
	info('Unmounting filesystems...')

	# Check if anything is mounted at the mount point
	mounted = get_lsblk_by_mountpoint(mount_point, as_prefix=True)

	if not mounted:
		info('No filesystems to unmount')
		return

	# Unmount recursively using SysCommand for better control
	max_attempts = 3
	for attempt in range(max_attempts):
		try:
			SysCommand(['umount', '--recursive', str(mount_point)])
			info('All filesystems unmounted successfully')
			return
		except SysCallError:
			if attempt < max_attempts - 1:
				warn(f'Unmount attempt {attempt + 1} failed, retrying...')
				import time

				time.sleep(1)
			else:
				error('Failed to unmount all filesystems. You may need to unmount manually.')


def unlock_luks_partition(partition: LsblkInfo) -> Luks2 | None:
	"""Prompt for password and unlock a LUKS partition."""
	info(f'Found encrypted partition: {partition.path}')

	# Generate a mapper name based on the partition
	mapper_name = f'rescue_{partition.name}'

	max_attempts = 3
	for attempt in range(max_attempts):
		try:
			password = getpass(f'Enter password for {partition.path}: ')
			if not password:
				warn('Empty password, skipping...')
				return None

			luks = Luks2(
				luks_dev_path=partition.path,
				mapper_name=mapper_name,
				password=Password(password),
			)

			luks.unlock()
			info(f'Successfully unlocked {partition.path} -> /dev/mapper/{mapper_name}')
			return luks

		except (DiskError, SysCallError) as e:
			remaining = max_attempts - attempt - 1
			if remaining > 0:
				warn(f'Failed to unlock: {e}. {remaining} attempt(s) remaining.')
			else:
				error(f'Failed to unlock {partition.path} after {max_attempts} attempts')

	return None


def select_partition(partitions: list[LsblkInfo]) -> LsblkInfo | None:
	"""Display a menu for the user to select a partition."""

	def _preview_partition(item: MenuItem) -> str | None:
		partition: LsblkInfo = item.get_value()
		lines = [
			f'Device: {partition.path}',
			f'Name: {partition.name}',
			f'Filesystem: {partition.fstype or "Unknown"}',
			f'Size: {partition.size.format_size(Unit.GiB)}',
			f'UUID: {partition.uuid or "None"}',
		]
		if partition.mountpoints:
			lines.append(f'Currently mounted: {", ".join(str(mp) for mp in partition.mountpoints)}')
		return '\n'.join(lines)

	# Create menu items
	menu_items = []
	for partition in partitions:
		label = f'{partition.name} ({partition.path})'
		if partition.fstype:
			label += f' [{partition.fstype}]'
		label += f' - {partition.size.format_size(Unit.GiB)}'

		item = MenuItem(
			text=label,
			value=partition,
			preview_action=_preview_partition,
		)
		menu_items.append(item)

	group = MenuItemGroup(menu_items, sort_items=False)

	result = SelectMenu[LsblkInfo](
		group,
		alignment=Alignment.CENTER,
		header='Select a partition containing the Linux installation to rescue:',
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case _:
			return None


def select_luks_partitions(partitions: list[LsblkInfo]) -> list[LsblkInfo]:
	"""Display a menu for the user to select LUKS partitions to unlock."""

	def _preview_partition(item: MenuItem) -> str | None:
		partition: LsblkInfo = item.get_value()
		lines = [
			f'Device: {partition.path}',
			f'Name: {partition.name}',
			'Type: LUKS encrypted',
			f'Size: {partition.size.format_size(Unit.GiB)}',
			f'UUID: {partition.uuid or "None"}',
		]
		return '\n'.join(lines)

	menu_items = []
	for partition in partitions:
		label = f'{partition.name} ({partition.path}) - {partition.size.format_size(Unit.GiB)}'

		item = MenuItem(
			text=label,
			value=partition,
			preview_action=_preview_partition,
		)
		menu_items.append(item)

	group = MenuItemGroup(menu_items, sort_items=False)

	result = SelectMenu[LsblkInfo](
		group,
		alignment=Alignment.CENTER,
		header='Select encrypted partition(s) to unlock (or skip if none):',
		allow_skip=True,
		allow_reset=True,
		multi=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			value = result.get_value()
			# multi=True returns a list, but type system doesn't know
			return value if isinstance(value, list) else [value]
		case _:
			return []


def rescue() -> None:
	"""Main rescue mode entry point."""
	config_handler = get_arch_config_handler()
	args = config_handler.args

	info('This utility will help you mount and chroot into an existing installation.')

	# Track unlocked LUKS devices for cleanup
	unlocked_luks: list[Luks2] = []

	# Initialize device handler
	handler = DeviceHandler()

	# Activate LVM volume groups first
	info('Activating LVM volume groups...')
	activate_lvm_volumes()

	# Get all block devices
	info('Scanning for block devices...')
	all_devices = get_all_lsblk_info()

	# Check for LUKS encrypted partitions
	luks_partitions = find_luks_partitions(all_devices)

	if luks_partitions:
		info(f'Found {len(luks_partitions)} encrypted partition(s)')

		# Let user select which LUKS partitions to unlock
		with Tui():
			selected_luks = select_luks_partitions(luks_partitions)

		for luks_part in selected_luks:
			luks = unlock_luks_partition(luks_part)
			if luks:
				unlocked_luks.append(luks)

		# Rescan devices after unlocking
		if unlocked_luks:
			info('Rescanning devices after unlocking...')
			# Re-activate LVM in case there's LVM on LUKS
			activate_lvm_volumes()
			all_devices = get_all_lsblk_info()

	# Find potential Linux partitions
	linux_partitions = find_linux_partitions(all_devices)

	if not linux_partitions:
		error('No Linux partitions found. Make sure your disks are properly connected.')
		# Cleanup: lock any unlocked LUKS devices
		for luks in unlocked_luks:
			with contextlib.suppress(DiskError, SysCallError):
				luks.lock()
		return

	info(f'Found {len(linux_partitions)} potential Linux partition(s)')

	# Let user select a partition
	with Tui():
		selected_partition = select_partition(linux_partitions)

	if not selected_partition:
		info('No partition selected. Exiting rescue mode.')
		# Cleanup: lock any unlocked LUKS devices
		for luks in unlocked_luks:
			with contextlib.suppress(DiskError, SysCallError):
				luks.lock()
		return

	info(f'Selected partition: {selected_partition.path}')

	# Create temporary mount point
	mount_point = args.mountpoint

	# Ensure mount point exists
	mount_point.mkdir(parents=True, exist_ok=True)

	# Mount the root partition
	if not mount_partition(selected_partition, mount_point, handler):
		# Cleanup: lock any unlocked LUKS devices
		for luks in unlocked_luks:
			with contextlib.suppress(DiskError, SysCallError):
				luks.lock()
		return

	# Verify it's a Linux root filesystem
	if not verify_linux_root(mount_point):
		error(f'{selected_partition.path} does not appear to contain a valid Linux root filesystem.')
		unmount_all(mount_point)
		# Cleanup: lock any unlocked LUKS devices
		for luks in unlocked_luks:
			with contextlib.suppress(DiskError, SysCallError):
				luks.lock()
		return

	info('Linux root filesystem verified!')

	# Mount additional filesystems from fstab
	mount_additional_filesystems(mount_point, handler)

	# Display information
	info(f'Installation mounted at: {mount_point}')
	info('Entering chroot environment...')
	info('Note: arch-chroot will automatically mount /dev, /proc, /sys, and handle DNS.')
	info('Type "exit" to leave the chroot and return to the live environment.')

	# Use arch-chroot directly
	try:
		SysCommand(['arch-chroot', str(mount_point)], peek_output=True)
	except SysCallError:
		# Non-zero exit is normal when user types 'exit'
		pass
	except KeyboardInterrupt:
		info('\nChroot interrupted.')

	# Cleanup
	unmount_all(mount_point)

	# Lock any unlocked LUKS devices
	if unlocked_luks:
		info('Locking encrypted partitions...')
		for luks in unlocked_luks:
			try:
				luks.lock()
				info(f'Locked {luks.luks_dev_path}')
			except (DiskError, SysCallError) as e:
				warn(f'Failed to lock {luks.luks_dev_path}: {e}')

	info('Rescue mode completed.')


rescue()
