import sys
from pathlib import Path

from archinstall import debug, error
from archinstall.lib.args import ArchConfig, get_arch_config_handler
from archinstall.lib.configuration import ConfigurationHandler
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.disk.utils import disk_layouts
from archinstall.lib.global_menu import GlobalMenu
from archinstall.lib.installer import Installer
from archinstall.tui import Tui


def ask_user_questions(config: ArchConfig) -> None:
	with Tui():
		global_menu = GlobalMenu(config)
		global_menu.disable_all()

		global_menu.set_enabled('archinstall_language', True)
		global_menu.set_enabled('disk_config', True)
		global_menu.set_enabled('__config__', True)

		global_menu.run()


def perform_installation(mountpoint: Path, config: ArchConfig) -> None:
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	if not config.disk_config:
		error('No disk configuration provided')
		return

	disk_config = config.disk_config
	mountpoint = disk_config.mountpoint if disk_config.mountpoint else mountpoint

	with Installer(
		mountpoint,
		disk_config,
		kernels=config.kernels,
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

	if not args.silent:
		ask_user_questions(config)

	config_handler = ConfigurationHandler(config)
	config_handler.write_debug()
	config_handler.save()

	if args.dry_run:
		sys.exit(0)

	if not args.silent:
		aborted = False
		with Tui():
			if not config_handler.confirm_config():
				debug('Installation aborted')
				aborted = True

		if aborted:
			return format_disk()

	if disk_config := config.disk_config:
		fs_handler = FilesystemHandler(disk_config)
		fs_handler.perform_filesystem_operations()

	perform_installation(args.mountpoint, config)


format_disk()
