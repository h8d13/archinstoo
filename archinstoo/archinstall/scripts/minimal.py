from pathlib import Path

from archinstall.default_profiles.minimal import MinimalProfile
from archinstall.lib.args import ArchConfig, ArchConfigHandler, get_arch_config_handler
from archinstall.lib.configuration import ConfigurationHandler
from archinstall.lib.disk.device_handler import DeviceHandler
from archinstall.lib.disk.disk_menu import DiskLayoutConfigurationMenu
from archinstall.lib.disk.filesystem import FilesystemHandler
from archinstall.lib.installer import Installer
from archinstall.lib.models import Bootloader
from archinstall.lib.models.profile import ProfileConfiguration
from archinstall.lib.models.users import Password, User
from archinstall.lib.network.network_handler import NetworkHandler
from archinstall.lib.output import debug, error, info
from archinstall.lib.profile.profiles_handler import ProfileHandler
from archinstall.lib.tui import Tui


def perform_installation(
	mountpoint: Path,
	config: ArchConfig,
	handler: ArchConfigHandler,
	device_handler: DeviceHandler,
	profile_handler: ProfileHandler,
	network_handler: NetworkHandler,
) -> None:
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
		# Strap in the base system, add a bootloader and configure
		# some other minor details as specified by this profile and user.
		installation.mount_ordered_layout()
		installation.minimal_installation()
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
		profile_handler.install_profile_config(installation, profile_config)

		user = User('devel', Password(plaintext='devel'), False)
		installation.create_users(user)

	# Once this is done, we output some useful information to the user
	# And the installation is complete.
	info('There are two new accounts in your installation after reboot:')
	info(' * root (password: airoot)')
	info(' * devel (password: devel)')


def _minimal() -> None:
	handler = get_arch_config_handler()
	config = handler.config
	args = handler.args

	# Create handler instances once at the entry point and pass them through
	device_handler = DeviceHandler()
	profile_handler = ProfileHandler()
	network_handler = NetworkHandler()

	with Tui():
		disk_config = DiskLayoutConfigurationMenu(disk_layout_config=None).run()

	if disk_config is None:
		info('Installation cancelled.')
		return None

	config.disk_config = disk_config
	config_handler = ConfigurationHandler(config)
	config_handler.write_debug()
	config_handler.save()

	if args.dry_run:
		raise SystemExit(0)

	with Tui():
		if not config_handler.confirm_config():
			debug('Installation aborted')
			return _minimal()

	if (disk_config := config.disk_config) is not None:
		fs_handler = FilesystemHandler(disk_config, device_handler=device_handler)
		fs_handler.perform_filesystem_operations()

	perform_installation(args.mountpoint, config, handler, device_handler, profile_handler, network_handler)
	return None


_minimal()
