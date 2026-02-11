from archinstoo import debug, info
from archinstoo.lib.args import ArchConfig, get_arch_config_handler
from archinstoo.lib.configuration import ConfigurationHandler
from archinstoo.lib.disk.device_handler import DeviceHandler
from archinstoo.lib.disk.filesystem import FilesystemHandler
from archinstoo.lib.disk.utils import disk_layouts
from archinstoo.lib.global_menu import GlobalMenu
from archinstoo.lib.tui import Tui


def show_menu(config: ArchConfig) -> None:
	with Tui():
		global_menu = GlobalMenu(config, skip_auth=True)
		global_menu.disable_all()

		global_menu.set_enabled('archinstoo_language', True)
		global_menu.set_enabled('disk_config', True)
		global_menu.set_enabled('__config__', True)

		# Bypass mandatory checks for format-only mode
		global_menu._item_group.find_by_key('timezone').mandatory = False

		global_menu.run(additional_title='Format only')


def format_disk() -> None:
	handler = get_arch_config_handler()
	config = handler.config
	args = handler.args

	# Set script name for format mode
	config.script = 'format'

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
			debug('Configuration aborted')

	if disk_config := config.disk_config:
		fs_handler = FilesystemHandler(disk_config, device_handler=device_handler)
		fs_handler.perform_filesystem_operations()
		info('Disk formatting completed successfully')
	else:
		info('No disk configuration provided')

	debug(f'Disk states after formatting:\n{disk_layouts()}')


format_disk()
