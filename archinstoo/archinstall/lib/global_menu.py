import sys
from typing import override

from archinstall.lib.disk.disk_menu import DiskLayoutConfigurationMenu
from archinstall.lib.models.application import ApplicationConfiguration, ZramConfiguration
from archinstall.lib.models.authentication import AuthenticationConfiguration
from archinstall.lib.models.device import DiskLayoutConfiguration, DiskLayoutType, EncryptionType, FilesystemType, PartitionModification
from archinstall.lib.pm import list_available_packages
from archinstall.lib.tui.curses_menu import SelectMenu, Tui
from archinstall.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.lib.tui.result import ResultType
from archinstall.lib.tui.script_editor import edit_script
from archinstall.lib.tui.types import Alignment, Orientation

from .applications.application_menu import ApplicationMenu
from .args import ArchConfig
from .authentication.authentication_menu import AuthenticationMenu
from .bootloader.bootloader_menu import BootloaderMenu
from .configuration import ConfigurationHandler
from .hardware import SysInfo
from .interactions.general_conf import (
	add_number_of_parallel_downloads,
	ask_additional_packages_to_install,
	ask_for_a_timezone,
	ask_hostname,
	ask_ntp,
)
from .interactions.system_conf import ask_for_swap, select_kernel
from .locale.locale_menu import LocaleMenu
from .menu.abstract_menu import CONFIG_KEY, AbstractMenu
from .models.bootloader import Bootloader, BootloaderConfiguration
from .models.locale import LocaleConfiguration
from .models.mirrors import PacmanConfiguration
from .models.network import NetworkConfiguration, NicType
from .models.packages import Repository
from .models.profile import ProfileConfiguration
from .network.network_menu import ask_to_configure_network
from .output import FormattedOutput
from .pm.config import PacmanConfig
from .pm.mirrors import MirrorMenu
from .translationhandler import Language, tr, translation_handler


class GlobalMenu(AbstractMenu[None]):
	def __init__(self, arch_config: ArchConfig) -> None:
		self._arch_config = arch_config
		menu_options = self._get_menu_options()

		self._item_group = MenuItemGroup(
			menu_options,
			sort_items=False,
			checkmarks=True,
		)

		super().__init__(self._item_group, config=arch_config)

		# Apply pacman config if loaded from file
		if arch_config.pacman_config:
			PacmanConfig.apply_config(arch_config.pacman_config)

	def _get_menu_options(self) -> list[MenuItem]:
		menu_options = [
			MenuItem(
				text=tr('Archinstoo settings'),
				action=self._select_archinstall_settings,
				preview_action=self._prev_archinstall_settings,
				key='archinstall_language',  # syncs language to config, theme is session-only
			),
			MenuItem.separator(),  # critical - assumed empty and mandatory
			MenuItem(
				text=tr('Disk config'),
				action=self._select_disk_config,
				preview_action=self._prev_disk_config,
				mandatory=True,
				key='disk_config',
				value_validator=self._validate_disk_config,
			),
			MenuItem(
				text=tr('Authentication'),
				action=self._select_authentication,
				preview_action=self._prev_authentication,
				key='auth_config',
				value_validator=self._validate_auth_config,
			),
			MenuItem.separator(),  # resumed choices - from cfg json file
			MenuItem(
				text=tr('Locales'),
				action=self._locale_selection,
				preview_action=self._prev_locale,
				key='locale_config',
			),
			MenuItem(
				text=tr('Pacman config'),
				action=self._pacman_configuration,
				preview_action=self._prev_pacman_config,
				key='pacman_config',
			),
			MenuItem(
				text=tr('Bootloader'),
				value=BootloaderConfiguration.get_default(),
				action=self._select_bootloader_config,
				preview_action=self._prev_bootloader_config,
				key='bootloader_config',
			),
			MenuItem(
				text=tr('Swap'),
				value=ZramConfiguration(enabled=True),
				action=ask_for_swap,
				preview_action=self._prev_swap,
				key='swap',
			),
			MenuItem(
				text=tr('Kernels'),
				value=['linux'],
				action=self._select_kernel,
				preview_action=self._prev_kernel,
				mandatory=True,
				key='kernels',
			),
			MenuItem(
				text=tr('Profile'),
				action=self._select_profile,
				preview_action=self._prev_profile,
				key='profile_config',
			),
			MenuItem(
				text=tr('Hostname'),
				value='archlinux',
				action=ask_hostname,
				preview_action=self._prev_hostname,
				key='hostname',
			),
			MenuItem(
				text=tr('Applications'),
				action=self._select_applications,
				value=[],
				preview_action=self._prev_applications,
				key='app_config',
			),
			MenuItem(
				text=tr('Network config'),
				action=ask_to_configure_network,
				value={},
				preview_action=self._prev_network_config,
				key='network_config',
			),
			MenuItem(
				text=tr('Parallel Downloads'),
				action=add_number_of_parallel_downloads,
				value=0,
				preview_action=self._prev_parallel_dw,
				key='parallel_downloads',
			),
			MenuItem(
				text=tr('Timezone'),
				action=ask_for_a_timezone,
				value=None,
				preview_action=self._prev_tz,
				mandatory=True,
				key='timezone',
			),
			MenuItem(
				text=tr('Automatic time sync'),
				action=ask_ntp,
				value=True,
				preview_action=self._prev_ntp,
				key='ntp',
			),
			MenuItem(
				text=tr('Additional packages'),
				action=self._select_additional_packages,
				value=[],
				preview_action=self._prev_additional_pkgs,
				key='packages',
			),
			MenuItem(
				text=tr('Custom commands'),
				action=self._edit_custom_commands,
				value=[],
				preview_action=self._prev_custom_commands,
				key='custom_commands',
			),
			MenuItem.separator(),
			MenuItem(
				text=tr('Install'),
				preview_action=self._prev_install_invalid_config,
				key=f'{CONFIG_KEY}_install',
			),
			MenuItem(
				text=tr('Abort'),
				action=self._handle_abort,
				key=f'{CONFIG_KEY}_abort',
			),
		]

		return menu_options

	def _missing_configs(self) -> list[str]:
		item: MenuItem = self._item_group.find_by_key('auth_config')
		auth_config: AuthenticationConfiguration | None = item.value

		def check(s: str) -> bool:
			item = self._item_group.find_by_key(s)
			return item.has_value()

		missing = set()
		has_superuser = auth_config.has_elevated_users if auth_config else False

		if (auth_config is None or auth_config.root_enc_password is None) and not has_superuser:
			missing.add(
				tr('Either root-password or at least 1 user with sudo privileges must be specified'),
			)

		for item in self._item_group.items:
			if item.mandatory:
				assert item.key is not None
				if not check(item.key):
					missing.add(item.text)

		return list(missing)

	@override
	def _is_config_valid(self) -> bool:
		"""
		Checks the validity of the current configuration.
		"""
		if len(self._missing_configs()) != 0:
			return False
		return self._validate_bootloader() is None

	def _select_archinstall_settings(self, preset: Language) -> Language:
		"""Open settings submenu for language and theme selection."""
		items = [
			MenuItem(text=tr('Language'), key='lang'),
			MenuItem(text=tr('Theme'), key='theme'),
		]

		result = SelectMenu[None](
			MenuItemGroup(items, sort_items=False),
			header=tr('Archinstoo Settings'),
			alignment=Alignment.CENTER,
			allow_skip=True,
		).run()

		if result.type_ == ResultType.Selection:
			match result.item().key:
				case 'lang':
					preset = self._select_archinstall_language(preset)
				case 'theme':
					self._select_theme()

		return preset

	def _select_archinstall_language(self, preset: Language) -> Language:
		from .interactions.general_conf import select_archinstall_language

		language = select_archinstall_language(translation_handler.translated_languages, preset)
		translation_handler.activate(language)

		self._update_lang_text()

		return language

	def _select_theme(self) -> None:
		"""Select a theme for the TUI (session-only, not persisted)."""
		# Select mode (dark/light)
		mode_items = [
			MenuItem(text=tr('Dark'), value='dark'),
			MenuItem(text=tr('Light'), value='light'),
		]

		mode_group = MenuItemGroup(mode_items, sort_items=False)
		mode_group.set_focus_by_value(Tui._mode)

		mode_result = SelectMenu[str](
			mode_group,
			header=tr('Select mode'),
			alignment=Alignment.CENTER,
			allow_skip=True,
		).run()

		if mode_result.type_ == ResultType.Selection:
			if mode := mode_result.get_value():
				Tui.set_mode(mode)

		# Select accent color
		accent_items = [
			MenuItem(text=tr('Cyan'), value='cyan'),
			MenuItem(text=tr('Green'), value='green'),
			MenuItem(text=tr('Red'), value='red'),
			MenuItem(text=tr('Orange'), value='orange'),
			MenuItem(text=tr('Blue'), value='blue'),
			MenuItem(text=tr('Magenta'), value='magenta'),
		]

		accent_group = MenuItemGroup(accent_items, sort_items=False)
		accent_group.set_focus_by_value(Tui._accent)

		accent_result = SelectMenu[str](
			accent_group,
			header=tr('Select accent color'),
			alignment=Alignment.CENTER,
			allow_skip=True,
		).run()

		if accent_result.type_ == ResultType.Selection:
			if accent := accent_result.get_value():
				Tui.set_accent(accent)

		# Apply theme changes
		if t := Tui._t:
			t._set_up_colors()
			t.screen.clear()
			t.screen.refresh()

	def _prev_archinstall_settings(self, item: MenuItem) -> str | None:
		output = ''

		if lang := item.value:
			output += f'{tr("Language")}: {lang.display_name}\n'

		output += f'{tr("Theme")}: {Tui._mode.capitalize()} / {Tui._accent.capitalize()}'

		return output

	def _select_applications(self, preset: ApplicationConfiguration | None) -> ApplicationConfiguration | None:
		app_config = ApplicationMenu(preset).run()
		return app_config

	def _select_authentication(self, preset: AuthenticationConfiguration | None) -> AuthenticationConfiguration | None:
		auth_config = AuthenticationMenu(preset).run()
		return auth_config

	def _update_lang_text(self) -> None:
		"""
		The options for the global menu are generated with a static text;
		each entry of the menu needs to be updated with the new translation
		"""
		new_options = self._get_menu_options()

		for o in new_options:
			if o.key is not None:
				self._item_group.find_by_key(o.key).text = o.text

	def _locale_selection(self, preset: LocaleConfiguration) -> LocaleConfiguration:
		locale_config = LocaleMenu(preset).run()
		return locale_config

	def _prev_locale(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		config: LocaleConfiguration = item.value
		return config.preview()

	def _prev_network_config(self, item: MenuItem) -> str | None:
		if item.value:
			network_config: NetworkConfiguration = item.value
			if network_config.type == NicType.MANUAL:
				output = FormattedOutput.as_table(network_config.nics)
			else:
				output = f'{tr("Network configuration")}:\n{network_config.type.display_msg()}'

			return output
		return None

	def _prev_additional_pkgs(self, item: MenuItem) -> str | None:
		if item.value:
			title = tr('Additionals')
			divider = '-' * len(title)
			packages = '\n'.join(sorted(item.value))
			return f'{title}\n{divider}\n{packages}'
		return None

	def _prev_authentication(self, item: MenuItem) -> str | None:
		if item.value:
			auth_config: AuthenticationConfiguration = item.value
			output = ''

			if auth_config.root_enc_password:
				output += f'{tr("Root password")}: {auth_config.root_enc_password.hidden()}\n'

			if auth_config.users:
				output += FormattedOutput.as_table(auth_config.users) + '\n'
				output += f'{tr("Privilege esc")}: {auth_config.privilege_escalation.value}\n'

			return output

		return None

	def _validate_auth_config(self, auth_config: AuthenticationConfiguration) -> bool:
		return auth_config.root_enc_password is not None or len(auth_config.users) > 0

	def _validate_disk_config(self, disk_config: DiskLayoutConfiguration) -> bool:
		if enc := disk_config.disk_encryption:
			if enc.encryption_type != EncryptionType.NoEncryption:
				return enc.encryption_password is not None
		return True

	def _prev_applications(self, item: MenuItem) -> str | None:
		if item.value:
			app_config: ApplicationConfiguration = item.value
			output = ''

			if app_config.bluetooth_config:
				output += f'{tr("Bluetooth")}: '
				output += tr('Enabled') if app_config.bluetooth_config.enabled else tr('Disabled')
				output += '\n'

			if app_config.audio_config:
				audio_config = app_config.audio_config
				output += f'{tr("Audio")}: {audio_config.audio.value}'
				output += '\n'

			if app_config.print_service_config:
				output += f'{tr("Print service")}: '
				output += tr('Enabled') if app_config.print_service_config.enabled else tr('Disabled')
				output += '\n'

			if app_config.power_management_config:
				power_management_config = app_config.power_management_config
				output += f'{tr("Power management")}: {power_management_config.power_management.value}'
				output += '\n'

			if app_config.firewall_config:
				firewall_config = app_config.firewall_config
				output += f'{tr("Firewall")}: {firewall_config.firewall.value}'
				output += '\n'

			if app_config.management_config and app_config.management_config.tools:
				tools = ', '.join([t.value for t in app_config.management_config.tools])
				output += f'{tr("Management")}: {tools}'
				output += '\n'

			if app_config.monitor_config:
				monitor_config = app_config.monitor_config
				output += f'{tr("Monitor")}: {monitor_config.monitor.value}'
				output += '\n'

			if app_config.editor_config:
				editor_config = app_config.editor_config
				output += f'{tr("Editor")}: {editor_config.editor.value}'
				output += '\n'

			return output

		return None

	def _prev_tz(self, item: MenuItem) -> str | None:
		if item.value:
			return f'{tr("Timezone")}: {item.value}'
		return None

	def _prev_ntp(self, item: MenuItem) -> str | None:
		if item.value is not None:
			output = f'{tr("NTP")}: '
			output += tr('Enabled') if item.value else tr('Disabled')
			return output
		return None

	def _edit_custom_commands(self, preset: list[str]) -> list[str]:
		current_script = '\n'.join(preset) if preset else ''
		result = edit_script(preset=current_script, title=tr('Custom Commands'))
		if result is not None:
			# Split by newlines and filter empty lines
			commands = [line for line in result.split('\n') if line.strip()]
			return commands
		return preset

	def _prev_custom_commands(self, item: MenuItem) -> str | None:
		commands: list[str] = item.value or []
		if commands:
			output = f'{tr("Commands")}: {len(commands)}\n'
			for i, cmd in enumerate(commands[:5]):
				display = cmd[:50] + '...' if len(cmd) > 50 else cmd
				output += f'  {i + 1}. {display}\n'
			if len(commands) > 5:
				output += f'  ... +{len(commands) - 5} more'
			return output
		return None

	def _prev_disk_config(self, item: MenuItem) -> str | None:
		disk_layout_conf: DiskLayoutConfiguration | None = item.value

		if disk_layout_conf:
			output = tr('Configuration type: {}').format(disk_layout_conf.config_type.display_msg()) + '\n'

			if disk_layout_conf.config_type == DiskLayoutType.Pre_mount:
				output += tr('Mountpoint') + ': ' + str(disk_layout_conf.mountpoint)

			if disk_layout_conf.lvm_config:
				output += '{}: {}'.format(tr('LVM configuration type'), disk_layout_conf.lvm_config.config_type.display_msg()) + '\n'

			if disk_layout_conf.disk_encryption:
				output += tr('Disk encryption') + ': ' + disk_layout_conf.disk_encryption.encryption_type.type_to_text() + '\n'

			if disk_layout_conf.btrfs_options:
				btrfs_options = disk_layout_conf.btrfs_options
				if btrfs_options.snapshot_config:
					output += tr('Btrfs snapshot type: {}').format(btrfs_options.snapshot_config.snapshot_type.value) + '\n'

			return output

		return None

	def _prev_swap(self, item: MenuItem) -> str | None:
		if item.value is not None:
			output = f'{tr("Swap on zram")}: '
			output += tr('Enabled') if item.value.enabled else tr('Disabled')
			if item.value.enabled:
				output += f'\n{tr("Compression algorithm")}: {item.value.algorithm.value}'
			return output
		return None

	def _prev_hostname(self, item: MenuItem) -> str | None:
		if item.value is not None:
			return f'{tr("Hostname")}: {item.value}'
		return None

	def _prev_parallel_dw(self, item: MenuItem) -> str | None:
		if item.value is not None:
			return f'{tr("Parallel Downloads")}: {item.value}'
		return None

	def _select_kernel(self, preset: list[str]) -> list[str]:
		"""Select kernels and then ask about kernel headers."""
		selected_kernels = select_kernel(preset)

		# Ask about kernel headers
		current_headers = self._arch_config.kernel_headers
		header_text = tr('Install kernel headers?') + '\n\n'
		header_text += tr('Useful for building out-of-tree drivers or DKMS modules,') + '\n'
		header_text += tr('especially for non-standard kernel variants.') + '\n'

		group = MenuItemGroup.yes_no()
		group.set_focus_by_value(current_headers)

		result = SelectMenu[bool](
			group,
			header=header_text,
			columns=2,
			orientation=Orientation.HORIZONTAL,
			alignment=Alignment.CENTER,
			allow_skip=True,
		).run()

		match result.type_:
			case ResultType.Skip:
				pass
			case ResultType.Selection:
				self._arch_config.kernel_headers = result.item() == MenuItem.yes()

		return selected_kernels

	def _prev_kernel(self, item: MenuItem) -> str | None:
		if item.value:
			kernel = ', '.join(item.value)
			output = f'{tr("Kernels")}: {kernel}\n'
			status = tr('Enabled') if self._arch_config.kernel_headers else tr('Disabled')
			output += f'{tr("Headers")}: {status}'
			return output
		return None

	def _prev_bootloader_config(self, item: MenuItem) -> str | None:
		bootloader_config: BootloaderConfiguration | None = item.value
		if bootloader_config:
			return bootloader_config.preview()
		return None

	def _validate_bootloader(self) -> str | None:
		"""
		Checks the selected bootloader is valid for the selected filesystem
		type of the boot partition.

		Returns [`None`] if the bootloader is valid, otherwise returns a
		string with the error message.

		XXX: The caller is responsible for wrapping the string with the translation
			shim if necessary.
		"""
		bootloader_config: BootloaderConfiguration | None = None
		root_partition: PartitionModification | None = None
		boot_partition: PartitionModification | None = None
		efi_partition: PartitionModification | None = None

		bootloader_config = self._item_group.find_by_key('bootloader_config').value

		if not bootloader_config or bootloader_config.bootloader == Bootloader.NO_BOOTLOADER:
			return None

		bootloader = bootloader_config.bootloader

		if disk_config := self._item_group.find_by_key('disk_config').value:
			for layout in disk_config.device_modifications:
				if root_partition := layout.get_root_partition():
					break
			for layout in disk_config.device_modifications:
				if boot_partition := layout.get_boot_partition():
					break
			if SysInfo.has_uefi():
				for layout in disk_config.device_modifications:
					if efi_partition := layout.get_efi_partition():
						break
		else:
			return 'No disk layout selected'

		if root_partition is None:
			return 'Root partition not found'

		if boot_partition is None:
			return 'Boot partition not found'

		if SysInfo.has_uefi():
			if efi_partition is None:
				return 'EFI system partition (ESP) not found'

			if efi_partition.fs_type not in [FilesystemType.Fat12, FilesystemType.Fat16, FilesystemType.Fat32]:
				return 'ESP must be formatted as a FAT filesystem'

		if bootloader == Bootloader.Limine:
			if boot_partition.fs_type not in [FilesystemType.Fat12, FilesystemType.Fat16, FilesystemType.Fat32]:
				return 'Limine does not support booting with a non-FAT boot partition'

		elif bootloader == Bootloader.Refind:
			if not SysInfo.has_uefi():
				return 'rEFInd can only be used on UEFI systems'

		return None

	def _prev_install_invalid_config(self, item: MenuItem) -> str | None:
		if missing := self._missing_configs():
			text = tr('Missing configurations:\n')
			for m in missing:
				text += f'- {m}\n'
			return text[:-1]  # remove last new line

		if error := self._validate_bootloader():
			return tr(f'Invalid configuration: {error}')

		return None

	def _prev_profile(self, item: MenuItem) -> str | None:
		profile_config: ProfileConfiguration | None = item.value

		if profile_config and profile_config.profile:
			output = tr('Profiles') + ': '
			if profile_names := profile_config.profile.current_selection_names():
				output += ', '.join(profile_names) + '\n'
			else:
				output += profile_config.profile.name + '\n'

			if profile_config.gfx_driver:
				output += tr('Graphics driver') + ': ' + profile_config.gfx_driver.value + '\n'

			if profile_config.greeter:
				output += tr('Greeter') + ': ' + profile_config.greeter.value + '\n'

			return output

		return None

	def _select_disk_config(
		self,
		preset: DiskLayoutConfiguration | None = None,
	) -> DiskLayoutConfiguration | None:
		disk_config = DiskLayoutConfigurationMenu(preset).run()

		return disk_config

	def _select_bootloader_config(
		self,
		preset: BootloaderConfiguration | None = None,
	) -> BootloaderConfiguration | None:
		if preset is None:
			preset = BootloaderConfiguration.get_default()

		bootloader_config = BootloaderMenu(preset).run()

		return bootloader_config

	def _select_profile(self, current_profile: ProfileConfiguration | None) -> ProfileConfiguration | None:
		from .profile.profile_menu import ProfileMenu

		kernels: list[str] | None = self._item_group.find_by_key('kernels').value
		profile_config = ProfileMenu(preset=current_profile, kernels=kernels).run()
		return profile_config

	def _select_additional_packages(self, preset: list[str]) -> list[str]:
		config: PacmanConfiguration | None = self._item_group.find_by_key('pacman_config').value

		repositories: set[Repository] = set()
		custom_repos: list[str] = []
		if config:
			repositories = set(config.optional_repositories)
			custom_repos = [r.name for r in config.custom_repositories]

		packages = ask_additional_packages_to_install(
			preset,
			repositories=repositories,
			custom_repos=custom_repos,
		)

		return packages

	def _pacman_configuration(self, preset: PacmanConfiguration | None = None) -> PacmanConfiguration:
		pacman_configuration = MirrorMenu(preset=preset).run()

		needs_apply = pacman_configuration.optional_repositories or pacman_configuration.custom_repositories or pacman_configuration.pacman_options

		if needs_apply:
			# reset the package list cache in case the repository selection has changed
			if pacman_configuration.optional_repositories or pacman_configuration.custom_repositories:
				list_available_packages.cache_clear()

			# enable the repositories and options in the config
			pacman_config = PacmanConfig(None)
			if pacman_configuration.optional_repositories:
				pacman_config.enable(pacman_configuration.optional_repositories)
			if pacman_configuration.custom_repositories:
				pacman_config.enable_custom(pacman_configuration.custom_repositories)
			if pacman_configuration.pacman_options:
				pacman_config.enable_options(pacman_configuration.pacman_options)
			pacman_config.apply()

		return pacman_configuration

	def _prev_pacman_config(self, item: MenuItem) -> str | None:
		if not item.value:
			return None

		config: PacmanConfiguration = item.value

		output = ''
		if config.mirror_regions:
			title = tr('Selected mirror regions')
			divider = '-' * len(title)
			regions = config.region_names
			output += f'{title}\n{divider}\n{regions}\n\n'

		if config.custom_servers:
			title = tr('Custom servers')
			divider = '-' * len(title)
			servers = config.custom_server_urls
			output += f'{title}\n{divider}\n{servers}\n\n'

		if config.optional_repositories:
			title = tr('Optional repositories')
			divider = '-' * len(title)
			repos = ', '.join([r.value for r in config.optional_repositories])
			output += f'{title}\n{divider}\n{repos}\n\n'

		if config.custom_repositories:
			title = tr('Custom repositories')
			table = FormattedOutput.as_table(config.custom_repositories)
			output += f'{title}:\n\n{table}'

		return output.strip()

	def _handle_abort(self, preset: None) -> None:
		items = []
		# Only offer to save if meaningful config has been set
		disk_config = self._item_group.find_by_key('disk_config').value
		profile_config = self._item_group.find_by_key('profile_config').value
		app_config = self._item_group.find_by_key('app_config').value

		if disk_config is not None or profile_config is not None or app_config:
			items.append(MenuItem(text=tr('save selections abort'), value='save_abort'))

		items.append(MenuItem(text=tr('exit delete selections'), value='abort_only'))
		items.append(MenuItem(text=tr('cancel abort'), value='cancel'))

		group = MenuItemGroup(items)
		group.focus_item = group.items[0]  # Focus on first option

		result = SelectMenu[str](
			group,
			header=tr('Abort the installation? \n'),
			alignment=Alignment.CENTER,
			allow_skip=False,
		).run()

		if result.type_ == ResultType.Selection:
			choice = result.get_value()

			if choice == 'save_abort':
				# Sync current selections to config before saving
				self.sync_all_to_config()
				config_output = ConfigurationHandler(self._arch_config)
				config_output.save()
				sys.exit(0)  # User-initiated abort is not an error
			elif choice == 'abort_only':
				ConfigurationHandler.delete_saved_config()
				sys.exit(0)  # User-initiated abort is not an error
			# If 'cancel', just return to menu

		return None
