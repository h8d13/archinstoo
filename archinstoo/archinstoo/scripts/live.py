import time
from pathlib import Path

from archinstoo.default_profiles.profile import DisplayServer
from archinstoo.lib.applications.application_handler import ApplicationHandler
from archinstoo.lib.args import ArchConfig, ArchConfigHandler, Arguments, get_arch_config_handler
from archinstoo.lib.authentication.shell import ShellApp
from archinstoo.lib.configuration import ConfigurationHandler
from archinstoo.lib.global_menu import GlobalMenu
from archinstoo.lib.installer import Installer, accessibility_tools_in_use, run_aur_installation, run_custom_user_commands
from archinstoo.lib.models.device import DiskLayoutConfiguration, DiskLayoutType
from archinstoo.lib.models.users import User
from archinstoo.lib.network.network_handler import NetworkHandler
from archinstoo.lib.output import debug, info
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.lib.tui import Tui


def show_menu(config: ArchConfig, args: Arguments) -> None:
	with Tui():
		global_menu = GlobalMenu(config, skip_boot=True, skip_auth=False, advanced=args.advanced)

		# Disable items irrelevant for live mode
		# We assume user built stage 1 but might still want to configure some stuff
		global_menu.set_enabled('bootloader_config', False)
		global_menu.set_enabled('kernels', False)
		global_menu.set_enabled('disk_config', False)
		global_menu.set_mandatory('disk_config', False)
		global_menu.set_mandatory('timezone', False)

		if not args.advanced:
			global_menu.set_enabled('aur_packages', False)
			global_menu.set_enabled('custom_commands', False)

		global_menu.run(additional_title='- Live mode')


def perform_installation(
	config: ArchConfig,
	args: Arguments,
	handler: ArchConfigHandler,
	profile_handler: ProfileHandler,
	application_handler: ApplicationHandler,
	network_handler: NetworkHandler,
) -> None:
	"""
	Configures the currently running system.
	Uses pacman -S instead of pacstrap, no disk ops, no bootloader, no kernel.
	"""
	start_time = time.monotonic()
	info('Starting live configuration...')

	# Dummy disk config — no actual disk operations
	disk_config = DiskLayoutConfiguration(
		config_type=DiskLayoutType.Pre_mount,
		device_modifications=[],
		mountpoint=Path('/'),
	)

	locale_config = config.locale_config

	with Installer(
		Path('/'),
		disk_config,
		kernels=[],
		handler=handler,
	) as installation:
		# Mark base and bootloader as done — we're on a running system
		installation.set_helper_flag('base', True)
		installation.set_helper_flag('bootloader', 'live')

		# Configure system basics
		if locale_config:
			installation.set_vconsole(locale_config)
			# Skip set_locale in live mode - system locale already configured

		if config.hostname:
			installation.set_hostname(config.hostname)

		if config.timezone and not installation.set_timezone(config.timezone):
			debug(f'Failed to set timezone: {config.timezone}')

		# Pacman mirror configuration
		if pacman_config := config.pacman_config:
			installation.set_mirrors(pacman_config, on_target=False)

		# Swap (zram)
		if config.swap and config.swap.enabled:
			installation.setup_swap('zram', algo=config.swap.algorithm)

		# Network
		if network_config := config.network_config:
			network_handler.install_network_config(
				network_config,
				installation,
				config.profile_config,
			)

		# Users
		if config.auth_config and config.auth_config.users:
			installation.create_users(
				config.auth_config.users,
				config.auth_config.privilege_escalation,
			)
			ShellApp().install(installation, config.auth_config.users)

		# Applications
		if app_config := config.app_config:
			users = config.auth_config.users if config.auth_config else None
			application_handler.install_applications(installation, app_config, users)

		# Profile (desktop environment, etc.)
		if profile_config := config.profile_config:
			profile_handler.install_profile_config(installation, profile_config)

			if profile_config.profiles and DisplayServer.X11 in profile_config.display_servers() and locale_config:
				installation.set_x11_keyboard(locale_config.kb_layout)

		# Additional packages
		if config.packages and config.packages[0] != '':
			installation.add_additional_packages(config.packages)

		# AUR packages
		if config.aur_packages and config.auth_config:
			run_aur_installation(config.aur_packages, installation, config.auth_config.users)

		# NTP
		if config.ntp:
			installation.activate_time_synchronization()

		# Accessibility
		if accessibility_tools_in_use():
			installation.enable_espeakup()

		# Root password
		if config.auth_config and config.auth_config.root_enc_password:
			root_user = User('root', config.auth_config.root_enc_password, False)
			installation.set_user_password(root_user)

			if config.auth_config.lock_root_account:
				installation.lock_root_account()

		# Post-install profile hooks
		if (profile_config := config.profile_config) and profile_config.profiles:
			for profile in profile_config.profiles:
				profile.post_install(installation)

		# Services
		if services := config.services:
			installation.enable_services_from_config(services)

		# Custom commands
		if args.advanced and (cc := config.custom_commands):
			run_custom_user_commands(cc, installation)

		# No genfstab — we're on a running system

		elapsed_time = time.monotonic() - start_time
		info(f'Live configuration completed in {elapsed_time:.1f}s')


def live() -> None:
	handler = get_arch_config_handler()
	args = handler.args
	config = handler.config

	# Override defaults for live mode
	args.skip_boot = True
	config.kernels = []

	profile_handler = ProfileHandler()
	application_handler = ApplicationHandler()
	network_handler = NetworkHandler()

	if cached := ConfigurationHandler.prompt_resume():
		try:
			handler.config = ArchConfig.from_config(cached, args)
			handler.config.kernels = []
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
		args,
		handler,
		profile_handler,
		application_handler,
		network_handler,
	)


live()
