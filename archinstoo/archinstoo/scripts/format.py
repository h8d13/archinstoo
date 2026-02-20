from pathlib import Path

from archinstoo import debug, error
from archinstoo.lib.args import ArchConfig, ArchConfigHandler, get_arch_config_handler
from archinstoo.lib.configuration import ConfigurationHandler
from archinstoo.lib.disk.device_handler import DeviceHandler
from archinstoo.lib.disk.filesystem import FilesystemHandler
from archinstoo.lib.disk.utils import disk_layouts
from archinstoo.lib.global_menu import GlobalMenu
from archinstoo.lib.installer import Installer
from archinstoo.lib.tui import Tui


def show_menu(config: ArchConfig) -> None:
	with Tui():
		global_menu = GlobalMenu(config)
		global_menu.disable_all()
		global_menu.run(additional_title=' - Format mode')

		global_menu.set_enabled('archinstoo_language', True)
		global_menu.set_enabled('disk_config', True)
		global_menu.set_enabled('__config__', True)

		global_menu.run()


def perform_installation(
	mountpoint: Path,
	config: ArchConfig,
	handler: ArchConfigHandler,
	device_handler: DeviceHandler,
) -> None:
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	if not config.disk_config:
		error('No disk configuration provided')
		return

	disk_config = config.disk_config
	mountpoint = disk_config.mountpoint or mountpoint

	with Installer(
		mountpoint,
		disk_config,
		kernels=config.kernels,
		handler=handler,
		device_handler=device_handler,
	) as installation:
		# Mount all the drives to the desired mountpoint
		# This *can* be done outside of the installation, but the installer can deal with it.
		installation.mount_ordered_layout()

		# to generate a fstab directory holder. Avoids an error on exit and at the same time checks the procedure
		target = Path(f'{mountpoint}/etc/fstab')
		if not target.parent.exists():
			target.parent.mkdir(parents=True)

	# For support reasons, we'll log the disk layout post installation (crash or no crash)
	debug(f'Disk states after installing:\n{disk_layouts()}')


def format_disk() -> None:
	handler = get_arch_config_handler()
	config = handler.config
	args = handler.args

	# Create handler instance once at the entry point and pass it through
	device_handler = DeviceHandler()

	while True:
		show_menu(config)

		config_handler = ConfigurationHandler(config)
		config_handler.write_debug()
		config_handler.save()

		if args.dry_run:
			raise SystemExit(0)

		with Tui():
			if config_handler.confirm_config():
				break
			debug('Installation aborted')

	if disk_config := config.disk_config:
		bootloader = config.bootloader_config.bootloader if config.bootloader_config else None
		fs_handler = FilesystemHandler(disk_config, device_handler=device_handler, bootloader=bootloader)
		fs_handler.perform_filesystem_operations()

	perform_installation(args.mountpoint, config, handler, device_handler)


format_disk()
