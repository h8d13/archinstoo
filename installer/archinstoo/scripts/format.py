from pathlib import Path

from archinstoo import debug, error, info
from archinstoo.lib.args import ArchConfig, ArchConfigHandler, Arguments, get_arch_config_handler
from archinstoo.lib.configuration import resolve_config
from archinstoo.lib.disk.device_handler import DeviceHandler
from archinstoo.lib.disk.filesystem import FilesystemHandler
from archinstoo.lib.disk.utils import disk_layouts
from archinstoo.lib.global_menu import GlobalMenu
from archinstoo.lib.installer import Installer
from archinstoo.lib.tui import Tui


def show_menu(config: ArchConfig, _args: Arguments) -> None:
	with Tui():
		# skip_auth/skip_boot: Install is refused while the auth and
		# bootloader checks still run against items this mode hides
		global_menu = GlobalMenu(config, skip_boot=True, skip_auth=True)
		global_menu.disable_all()

		global_menu.set_enabled('disk_config', True)
		global_menu.set_enabled('__config__', True)  # also enables session-only theme
		global_menu.set_mandatory('timezone', False)

		global_menu.run(additional_title='- Format mode')


def perform_installation(
	handler: ArchConfigHandler,
	device_handler: DeviceHandler,
) -> None:
	# Mounts the formatted layout and stops there.
	# Only requirement is that the block devices are
	# formatted and setup prior to entering this function.
	config = handler.config

	if not config.disk_config:
		error('No disk configuration provided')
		return

	disk_config = config.disk_config
	mountpoint = disk_config.mountpoint or handler.args.mountpoint

	with Installer(
		mountpoint,
		disk_config,
		kernels=config.kernels,
		handler=handler,
		device_handler=device_handler,
	) as installation:
		# format mode stops at a mounted layout: there is no base step to miss,
		# so claim it rather than let the exit summary report it as skipped
		installation.set_helper_flag('base', True)

		# Mount all the drives to the desired mountpoint
		# This *can* be done outside of the installation, but the installer can deal with it.
		info('Mounting the formatted layout...')
		installation.mount_ordered_layout()

		# to generate a fstab directory holder. Avoids an error on exit and at the same time checks the procedure
		target = Path(f'{mountpoint}/etc/fstab')
		if not target.parent.exists():
			target.parent.mkdir(parents=True)
			debug(f'Created {target.parent} to anchor fstab')

	# For support reasons, we'll log the disk layout post installation (crash or no crash)
	debug(f'Disk states after installing:\n{disk_layouts()}')


def _validate_silent(config: ArchConfig) -> None:
	if not config.disk_config:
		error('--silent needs disk_config in the config, nothing to format')
		raise SystemExit(1)


def format_disk() -> None:
	handler = get_arch_config_handler()

	# Create handler instance once at the entry point and pass it through
	device_handler = DeviceHandler()

	# same resolve/confirm path as guided, so --silent works here too
	config = resolve_config(handler, show_menu, validate_silent=_validate_silent)

	if disk_config := config.disk_config:
		fs_handler = FilesystemHandler(disk_config, device_handler=device_handler)
		fs_handler.perform_filesystem_operations()

	perform_installation(handler, device_handler)


format_disk()
