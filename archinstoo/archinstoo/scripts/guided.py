import contextlib
import os
import time
from pathlib import Path

from archinstoo import SysInfo
from archinstoo.default_profiles.profile import DisplayServer
from archinstoo.lib.applications.application_handler import ApplicationHandler
from archinstoo.lib.args import ArchConfig, ArchConfigHandler, Arguments, get_arch_config_handler
from archinstoo.lib.authentication.shell import ShellApp
from archinstoo.lib.configuration import ConfigurationHandler
from archinstoo.lib.disk.device_handler import DeviceHandler
from archinstoo.lib.disk.filesystem import FilesystemHandler
from archinstoo.lib.disk.utils import disk_layouts
from archinstoo.lib.global_menu import GlobalMenu
from archinstoo.lib.installer import Installer, accessibility_tools_in_use, run_aur_installation, run_custom_user_commands
from archinstoo.lib.interactions.general_conf import PostInstallationAction, select_post_installation
from archinstoo.lib.models import Bootloader
from archinstoo.lib.models.device import (
	DiskLayoutType,
	EncryptionType,
)
from archinstoo.lib.models.users import User
from archinstoo.lib.network.network_handler import NetworkHandler
from archinstoo.lib.output import debug, error, info
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.lib.tui import Tui


def show_menu(config: ArchConfig, args: Arguments) -> None:
	title_text = None

	with Tui():
		global_menu = GlobalMenu(config, args.skip_boot)

		if not args.advanced:
			global_menu.set_enabled('parallel_downloads', False)
			global_menu.set_enabled('aur_packages', False)
			global_menu.set_enabled('custom_commands', False)

		global_menu.run(additional_title=title_text)


def perform_installation(
	mountpoint: Path,
	config: ArchConfig,
	args: Arguments,
	handler: ArchConfigHandler,
	device_handler: DeviceHandler,
	profile_handler: ProfileHandler,
	application_handler: ApplicationHandler,
	network_handler: NetworkHandler,
) -> None:
	"""
	Performs the installation steps on a block device.
	Only requirement is that the block devices are
	formatted and setup prior to entering this function.
	"""
	start_time = time.monotonic()
	info('Starting installation...')

	if not config.disk_config:
		error('No disk configuration provided')
		return

	disk_config = config.disk_config
	run_mkinitcpio = not config.bootloader_config or not config.bootloader_config.uki
	locale_config = config.locale_config
	optional_repositories = config.pacman_config.optional_repositories if config.pacman_config else []
	mountpoint = disk_config.mountpoint or mountpoint

	with Installer(
		mountpoint,
		disk_config,
		kernels=config.kernels,
		handler=handler,
		device_handler=device_handler,
	) as installation:
		# Mount all the drives to the desired mountpoint
		if disk_config.config_type != DiskLayoutType.Pre_mount:
			installation.mount_ordered_layout()

		installation.sanity_check()

		if (
			disk_config.config_type != DiskLayoutType.Pre_mount
			and disk_config.disk_encryption
			and disk_config.disk_encryption.encryption_type != EncryptionType.NoEncryption
		):
			# generate encryption key files for the mounted luks devices
			installation.generate_key_files()

		if pacman_config := config.pacman_config:
			installation.set_mirrors(pacman_config, on_target=False)

		installation.minimal_installation(
			optional_repositories=optional_repositories,
			mkinitcpio=run_mkinitcpio,
			hostname=config.hostname,
			locale_config=locale_config,
			timezone=config.timezone,
		)

		if pacman_config := config.pacman_config:
			installation.set_mirrors(pacman_config, on_target=True)

		if config.swap and config.swap.enabled:
			installation.setup_swap('zram', algo=config.swap.algorithm)

		# Create users before applications (audio needs user for pipewire config)
		if config.auth_config and config.auth_config.users:
			installation.create_users(
				config.auth_config.users,
				config.auth_config.privilege_escalation,
			)
			ShellApp().install(installation, config.auth_config.users)

		# Install applications before bootloader so kernel params (e.g. AppArmor LSM) are included
		if app_config := config.app_config:
			users = config.auth_config.users if config.auth_config else None
			application_handler.install_applications(installation, app_config, users)

		if config.bootloader_config and config.bootloader_config.bootloader != Bootloader.NO_BOOTLOADER:
			if config.bootloader_config.bootloader == Bootloader.Grub and SysInfo.has_uefi():
				installation.add_additional_packages('grub')

			installation.add_bootloader(config.bootloader_config.bootloader, config.bootloader_config.uki, config.bootloader_config.removable)

		# If user selected to copy the current ISO network configuration
		# Perform a copy of the config
		if network_config := config.network_config:
			network_handler.install_network_config(
				network_config,
				installation,
				config.profile_config,
			)

		if profile_config := config.profile_config:
			profile_handler.install_profile_config(installation, profile_config)

			# Set X11 keyboard config if any profile uses X11
			if profile_config.profiles and DisplayServer.X11 in profile_config.display_servers() and locale_config:
				installation.set_x11_keyboard(locale_config.kb_layout)

		if config.packages and config.packages[0] != '':
			installation.add_additional_packages(config.packages)

		if config.kernel_headers:
			headers = [f'{kernel}-headers' for kernel in config.kernels]
			installation.add_additional_packages(headers)

		if config.aur_packages and config.auth_config:
			run_aur_installation(config.aur_packages, installation, config.auth_config.users)

		if config.ntp:
			installation.activate_time_synchronization()

		if accessibility_tools_in_use():
			installation.enable_espeakup()

		if config.auth_config and config.auth_config.root_enc_password:
			root_user = User('root', config.auth_config.root_enc_password, False)
			installation.set_user_password(root_user)

			if config.auth_config.lock_root_account:
				installation.lock_root_account()

		if (profile_config := config.profile_config) and profile_config.profiles:
			for profile in profile_config.profiles:
				profile.post_install(installation)

		# If the user provided a list of services to be enabled, pass the list to the enable_service function.
		# Note that while it's called enable_service, it can actually take a list of services and iterate it.
		if services := config.services:
			installation.enable_service(services)

		if disk_config.has_default_btrfs_vols():
			btrfs_options = disk_config.btrfs_options
			snapshot_config = btrfs_options.snapshot_config if btrfs_options else None
			snapshot_type = snapshot_config.snapshot_type if snapshot_config else None
			if snapshot_type:
				bootloader = config.bootloader_config.bootloader if config.bootloader_config else None
				installation.setup_btrfs_snapshot(snapshot_type, bootloader)

		# If the user provided custom commands to be run post-installation, execute them now.
		if args.advanced and (cc := config.custom_commands):
			run_custom_user_commands(cc, installation)

		installation.genfstab()

		debug(f'Disk states after installing:\n{disk_layouts()}')

		with Tui():
			elapsed_time = time.monotonic() - start_time
			action = select_post_installation(elapsed_time)

		match action:
			case PostInstallationAction.EXIT:
				pass
			case PostInstallationAction.REBOOT:
				os.system('reboot')
			case PostInstallationAction.POWEROFF:
				os.system('poweroff')
			case PostInstallationAction.CHROOT:
				with contextlib.suppress(Exception):
					installation.drop_to_shell()


def guided() -> None:
	handler = get_arch_config_handler()
	args = handler.args

	# Create handler instances once at the entry point and pass them through
	device_handler = DeviceHandler()
	profile_handler = ProfileHandler()
	application_handler = ApplicationHandler()
	network_handler = NetworkHandler()

	if cached := ConfigurationHandler.prompt_resume():
		try:
			handler._config = ArchConfig.from_config(cached, args)
			info('Saved selections loaded successfully')
		except Exception as e:
			error(f'Failed to load saved selections: {e}')

	while True:
		show_menu(handler.config, args)

		config = handler.config

		config_handler = ConfigurationHandler(config)
		config_handler.write_debug()
		config_handler.save()

		if args.dry_run:
			raise SystemExit(0)
			# just save config => no error

		with Tui():
			if config_handler.confirm_config():
				break
			debug('Installation aborted')

	if disk_config := config.disk_config:
		fs_handler = FilesystemHandler(disk_config, device_handler=device_handler)
		fs_handler.perform_filesystem_operations()

	perform_installation(
		args.mountpoint,
		config,
		args,
		handler,
		device_handler,
		profile_handler,
		application_handler,
		network_handler,
	)


guided()
