import time

from archinstoo.default_profiles.minimal import MinimalProfile
from archinstoo.lib.args import ArchConfig, ArchConfigHandler, Arguments, get_arch_config_handler
from archinstoo.lib.configuration import resolve_config
from archinstoo.lib.disk.device_handler import DeviceHandler
from archinstoo.lib.disk.disk_menu import DiskLayoutConfigurationMenu
from archinstoo.lib.disk.filesystem import FilesystemHandler
from archinstoo.lib.disk.utils import disk_layouts
from archinstoo.lib.installer import Installer
from archinstoo.lib.models import Bootloader
from archinstoo.lib.models.locale import LocaleConfiguration
from archinstoo.lib.models.users import Password, User
from archinstoo.lib.network.network_handler import NetworkHandler
from archinstoo.lib.output import debug, error, info
from archinstoo.lib.profile.config import ProfileConfiguration
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.lib.tui import Tui


def show_menu(config: ArchConfig, _args: Arguments) -> None:
	# only the disk layout is asked, everything else is fixed below
	with Tui():
		disk_config = DiskLayoutConfigurationMenu(config.disk_config).run()

	if disk_config is None:
		info('Installation cancelled.')
		raise SystemExit(0)

	config.disk_config = disk_config


def _validate_silent(config: ArchConfig) -> None:
	if not config.disk_config:
		error('--silent needs disk_config in the config, nothing to install to')
		raise SystemExit(1)


def perform_installation(
	handler: ArchConfigHandler,
	device_handler: DeviceHandler,
	profile_handler: ProfileHandler,
	network_handler: NetworkHandler,
) -> None:
	config = handler.config

	if not config.disk_config:
		error('No disk configuration provided')
		return

	disk_config = config.disk_config
	mountpoint = disk_config.mountpoint or handler.args.mountpoint

	start_time = time.monotonic()
	info('Starting minimal installation...')

	with Installer(
		mountpoint,
		disk_config,
		kernels=config.kernels,
		handler=handler,
		device_handler=device_handler,
	) as installation:
		# Strap in the base system, add a bootloader and configure
		# some other minor details as specified by this profile and user.
		installation.mount_ordered_layout()
		installation.minimal_installation(locale_config=LocaleConfiguration.default())
		installation.set_hostname('minimal-arch')
		installation.add_bootloader(Bootloader.Systemd)

		if network_config := config.network_config:
			network_handler.install_network_config(
				network_config,
				installation,
				config.profile_config,
			)

		installation.add_additional_packages(['nano', 'wget', 'git'])

		profile_config = ProfileConfiguration([MinimalProfile()])
		profile_handler.install_profile_config(installation, profile_config, config.app_config)

		user = User('devel', Password(plaintext='devel'), False)
		installation.create_users(user)

		# gpt-auto finds root and the ESP by partition type, so this installs
		# and boots without one: everything else (mkinitcpio and the bootloader
		# writing to a mounted /boot, rescue, swap) expects the real thing
		installation.genfstab()

	debug(f'Disk states after installing:\n{disk_layouts()}')
	info(f'Minimal installation completed in {time.monotonic() - start_time:.0f}s')

	# Once this is done, we output some useful information to the user
	# And the installation is complete.
	info('There are two new accounts in your installation after reboot:')
	info(' * root (password: airoot)')
	info(' * devel (password: devel)')


def _minimal() -> None:
	handler = get_arch_config_handler()

	# Create handler instances once at the entry point and pass them through
	device_handler = DeviceHandler()
	profile_handler = ProfileHandler()
	network_handler = NetworkHandler()

	# same resolve/save/confirm path as guided, so --silent and --dry-run work
	config = resolve_config(handler, show_menu, validate_silent=_validate_silent)

	if disk_config := config.disk_config:
		fs_handler = FilesystemHandler(disk_config, device_handler=device_handler)
		fs_handler.perform_filesystem_operations()

	perform_installation(handler, device_handler, profile_handler, network_handler)


_minimal()
