import time
from pathlib import Path

from archinstoo.lib.applications.application_handler import ApplicationHandler
from archinstoo.lib.args import ArchConfig, Arguments, get_arch_config_handler
from archinstoo.lib.configuration import ConfigurationHandler
from archinstoo.lib.global_menu import GlobalMenu
from archinstoo.lib.installer import Installer
from archinstoo.lib.models.device import DiskLayoutConfiguration, DiskLayoutType
from archinstoo.lib.output import debug, info
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.lib.tui import Tui


def show_menu(config: ArchConfig, args: Arguments) -> None:
	with Tui():
		global_menu = GlobalMenu(config, skip_boot=True, skip_auth=True)
		global_menu.disable_all()
		global_menu.run(additional_title='- Pkgs mode')

		# Only enable profile, applications, and packages
		global_menu.set_enabled('archinstoo_language', True)
		global_menu.set_enabled('profile_config', True)
		global_menu.set_enabled('app_config', True)
		global_menu.set_enabled('packages', True)
		global_menu.set_enabled('__config__', True)

		# Skip mandatory checks
		global_menu._item_group.find_by_key('timezone').mandatory = False
		global_menu._item_group.find_by_key('disk_config').mandatory = False

		global_menu.run(additional_title='Packages only')


def perform_installation(
	config: ArchConfig,
	profile_handler: ProfileHandler,
	application_handler: ApplicationHandler,
) -> None:
	"""
	Installs profiles, applications, and packages on the running system.
	No disk ops, no bootloader, no kernel, no users.
	"""
	start_time = time.monotonic()
	info('Starting package installation...')

	# Dummy disk config — no actual disk operations
	disk_config = DiskLayoutConfiguration(
		config_type=DiskLayoutType.Pre_mount,
		device_modifications=[],
		mountpoint=Path('/'),
	)

	with Installer(
		Path('/'),
		disk_config,
		kernels=[],
	) as installation:
		# Mark base and bootloader as done — we're on a running system
		installation._helper_flags['base'] = True
		installation._helper_flags['bootloader'] = 'packages'

		# Applications
		if app_config := config.app_config:
			application_handler.install_applications(installation, app_config, None)

		# Profile (desktop environment, etc.)
		if profile_config := config.profile_config:
			profile_handler.install_profile_config(installation, profile_config)

			# Post-install profile hooks
			if profile_config.profiles:
				for profile in profile_config.profiles:
					profile.post_install(installation)

		# Additional packages
		if config.packages and config.packages[0] != '':
			installation.add_additional_packages(config.packages)

		# Services
		if services := config.services:
			installation.enable_services_from_config(services)

		elapsed_time = time.monotonic() - start_time
		info(f'Package installation completed in {elapsed_time:.1f}s')


def packages() -> None:
	handler = get_arch_config_handler()
	args = handler.args
	config = handler.config

	# Set script name
	config.script = 'packages'

	profile_handler = ProfileHandler()
	application_handler = ApplicationHandler()

	if cached := ConfigurationHandler.prompt_resume():
		try:
			handler._config = ArchConfig.from_config(cached, args)
			info('Saved selections loaded successfully')
		except Exception as e:
			debug(f'Failed to load saved selections: {e}')

	while True:
		show_menu(handler.config, args)

		config = handler.config

		config_handler = ConfigurationHandler(config)
		config_handler.write_debug()
		config_handler.save()

		if args.dry_run:
			raise SystemExit(0)

		with Tui():
			if config_handler.confirm_config():
				break
			debug('Configuration aborted')

	perform_installation(
		config,
		profile_handler,
		application_handler,
	)


packages()
