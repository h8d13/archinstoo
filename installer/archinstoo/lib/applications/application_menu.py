from typing import override

from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.menu.abstract_menu import AbstractSubMenu
from archinstoo.lib.models.application import (
	EXPERIMENTAL_CPU_SCHEDULERS,
	ApplicationConfiguration,
	Audio,
	AudioConfiguration,
	BluetoothConfiguration,
	CPUScheduler,
	CPUSchedulerConfiguration,
	DevelopmentConfiguration,
	DevTool,
	DevToolConfiguration,
	Editor,
	EditorConfiguration,
	Firewall,
	FirewallConfiguration,
	FlatpakConfiguration,
	Language,
	LanguageConfiguration,
	Management,
	ManagementConfiguration,
	MediaCodecsConfiguration,
	Monitor,
	MonitorConfiguration,
	PowerManagement,
	PowerManagementConfiguration,
	PrintServiceConfiguration,
	Security,
	SecurityConfiguration,
	Terminal,
	TerminalConfiguration,
	ThunderboltConfiguration,
)
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.prompts import prompt_choice, prompt_yes_no
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties


class ApplicationMenu(AbstractSubMenu[ApplicationConfiguration]):
	def __init__(
		self,
		preset: ApplicationConfiguration | None = None,
		advanced: bool = False,
	) -> None:
		self._advanced = advanced

		if preset:
			self._app_config = preset
		else:
			self._app_config = ApplicationConfiguration()

		menu_options = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_options, checkmarks=True)

		super().__init__(
			self._item_group,
			config=self._app_config,
			allow_reset=True,
		)

	def preview_lines(self) -> list[str]:
		# every category preview, off the config this menu was handed
		return [text for entry in self._item_group.items if entry.preview_action and (text := entry.preview_action(entry))]

	@override
	def run(self, additional_title: str | None = None) -> ApplicationConfiguration:
		super().run(additional_title=additional_title)
		return self._app_config

	def _define_menu_options(self) -> list[MenuItem]:
		items = [
			MenuItem(
				text='Bluetooth',
				action=select_bluetooth,
				value=self._app_config.bluetooth_config,
				preview_action=self._prev_bluetooth,
				key='bluetooth_config',
			),
			MenuItem(
				text='Thunderbolt',
				action=select_thunderbolt,
				value=self._app_config.thunderbolt_config,
				preview_action=self._prev_thunderbolt,
				enabled=SysInfo.has_thunderbolt(),
				key='thunderbolt_config',
			),
			MenuItem(
				text='Audio',
				action=select_audio,
				preview_action=self._prev_audio,
				key='audio_config',
			),
			MenuItem(
				text='Print service',
				action=select_print_service,
				preview_action=self._prev_print_service,
				key='print_service_config',
			),
			MenuItem(
				text='Media codecs',
				action=select_media_codecs,
				preview_action=self._prev_media_codecs,
				key='media_codecs_config',
			),
			MenuItem(
				text='Flatpak',
				action=select_flatpak,
				preview_action=self._prev_flatpak,
				key='flatpak_config',
			),
			MenuItem(
				text='Power management',
				action=select_power_management,
				preview_action=self._prev_power_management,
				enabled=SysInfo.has_battery(),
				key='power_management_config',
			),
			MenuItem(
				text='Firewall',
				action=select_firewall,
				preview_action=self._prev_firewall,
				key='firewall_config',
			),
			MenuItem(
				text='Management',
				action=select_management,
				preview_action=self._prev_management,
				key='management_config',
			),
			MenuItem(
				text='Monitor',
				action=select_monitor,
				preview_action=self._prev_monitor,
				key='monitor_config',
			),
			MenuItem(
				text='Editor',
				action=select_editor,
				preview_action=self._prev_editor,
				key='editor_config',
			),
			MenuItem(
				text='Terminal',
				action=select_terminal,
				preview_action=self._prev_terminal,
				key='terminal_config',
			),
			MenuItem(
				text='Security',
				action=select_security,
				preview_action=self._prev_security,
				key='security_config',
			),
		]

		# development tooling and sched_ext are opt-in; only surfaced with --advanced
		if self._advanced:
			items.append(
				MenuItem(
					text='CPU scheduler',
					action=select_cpu_scheduler,
					preview_action=self._prev_cpu_scheduler,
					key='cpu_scheduler_config',
				),
			)
			items.append(
				MenuItem(
					text='Development',
					action=select_development,
					preview_action=self._prev_development,
					key='development_config',
				),
			)

		return items

	def _prev_power_management(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: PowerManagementConfiguration = item.value
			return f'{"Power management"}: {config.power_management.value}'
		return None

	def _prev_cpu_scheduler(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: CPUSchedulerConfiguration = item.value
			return f'{"CPU scheduler"}: {config.scheduler.value}'
		return None

	def _prev_bluetooth(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: BluetoothConfiguration = item.value
			return _enabled_text('Bluetooth', config.enabled)
		return None

	def _prev_thunderbolt(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: ThunderboltConfiguration = item.value
			return _enabled_text('Thunderbolt', config.enabled)
		return None

	def _prev_audio(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: AudioConfiguration = item.value
			return f'{"Audio"}: {config.audio.value}'
		return None

	def _prev_print_service(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: PrintServiceConfiguration = item.value
			return _enabled_text('Print service', config.enabled)
		return None

	def _prev_media_codecs(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: MediaCodecsConfiguration = item.value
			return _enabled_text('Media codecs', config.enabled)
		return None

	def _prev_flatpak(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: FlatpakConfiguration = item.value
			return _enabled_text('Flatpak', config.enabled)
		return None

	def _prev_firewall(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: FirewallConfiguration = item.value
			return f'{"Firewall"}: {config.firewall.value}'
		return None

	def _prev_management(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: ManagementConfiguration = item.value
			tools = ', '.join([t.value for t in config.tools])
			return f'{"Management"}: {tools}'
		return None

	def _prev_monitor(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: MonitorConfiguration = item.value
			return f'{"Monitor"}: {config.monitor.value}'
		return None

	def _prev_editor(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: EditorConfiguration = item.value
			return f'{"Editor"}: {config.editor.value}'
		return None

	def _prev_terminal(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: TerminalConfiguration = item.value
			return f'Terminal: {config.terminal.value}'
		return None

	def _prev_security(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: SecurityConfiguration = item.value
			tools = ', '.join([t.value for t in config.tools])
			return f'{"Security"}: {tools}'
		return None

	def _prev_development(self, item: MenuItem) -> str | None:
		if item.value is None:
			return None

		config: DevelopmentConfiguration = item.value
		lines = []

		if config.language_config and config.language_config.tools:
			tools = ', '.join([t.value for t in config.language_config.tools])
			lines.append(f'{"Languages"}: {tools}')

		if config.devtool_config and config.devtool_config.tools:
			tools = ', '.join([t.value for t in config.devtool_config.tools])
			lines.append(f'{"Build & Debug"}: {tools}')

		return '\n'.join(lines) if lines else None


class DevelopmentMenu(AbstractSubMenu[DevelopmentConfiguration]):
	def __init__(
		self,
		preset: DevelopmentConfiguration | None = None,
	) -> None:
		if preset:
			self._dev_config = preset
		else:
			self._dev_config = DevelopmentConfiguration()

		menu_options = self._define_menu_options()
		self._item_group = MenuItemGroup(menu_options, checkmarks=True)

		super().__init__(
			self._item_group,
			config=self._dev_config,
			allow_reset=True,
		)

	@override
	def run(self, additional_title: str | None = None) -> DevelopmentConfiguration:
		super().run(additional_title=additional_title)
		return self._dev_config

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text='Languages',
				action=select_languages,
				preview_action=self._prev_languages,
				key='language_config',
			),
			MenuItem(
				text='Build & Debug',
				action=select_devtools,
				preview_action=self._prev_devtools,
				key='devtool_config',
			),
		]

	def _prev_languages(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: LanguageConfiguration = item.value
			tools = ', '.join([t.value for t in config.tools])
			return f'{"Languages"}: {tools}'
		return None

	def _prev_devtools(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: DevToolConfiguration = item.value
			tools = ', '.join([t.value for t in config.tools])
			return f'{"Build & Debug"}: {tools}'
		return None


def select_power_management(preset: PowerManagementConfiguration | None = None) -> PowerManagementConfiguration | None:
	choice = prompt_choice(
		MenuItemGroup.from_enum(PowerManagement), preset.power_management if preset else None, frame='Power management', allow_reset=True
	)
	return PowerManagementConfiguration(choice) if choice else None


def select_cpu_scheduler(preset: CPUSchedulerConfiguration | None = None) -> CPUSchedulerConfiguration | None:
	items = [MenuItem(text='Stable', read_only=True)]
	items += [MenuItem(text=f'  {s.value}', value=s) for s in CPUScheduler if s not in EXPERIMENTAL_CPU_SCHEDULERS]
	items.append(MenuItem(text='Experimental', read_only=True))
	items += [MenuItem(text=f'  {s.value}', value=s) for s in CPUScheduler if s in EXPERIMENTAL_CPU_SCHEDULERS]

	choice = prompt_choice(items, preset.scheduler if preset else None, frame='CPU scheduler', allow_reset=True)
	return CPUSchedulerConfiguration(choice) if choice else None


def _enabled_text(label: str, enabled: bool) -> str:
	return f'{label}: {"Enabled" if enabled else "Disabled"}'


def select_bluetooth(preset: BluetoothConfiguration | None) -> BluetoothConfiguration | None:
	enabled = prompt_yes_no('Would you like to configure Bluetooth?' + '\n', preset.enabled if preset else False)
	return preset if enabled is None else BluetoothConfiguration(enabled)


def select_thunderbolt(preset: ThunderboltConfiguration | None) -> ThunderboltConfiguration | None:
	enabled = prompt_yes_no(
		'Would you like to configure Thunderbolt device authorization (bolt)?\n'
		'New devices are auto-enrolled when the desktop asks or IOMMU DMA protection is on,\n'
		'otherwise once with: boltctl enroll --policy auto <uuid>\n',
		preset.enabled if preset else False,
	)
	return preset if enabled is None else ThunderboltConfiguration(enabled)


def select_print_service(preset: PrintServiceConfiguration | None) -> PrintServiceConfiguration | None:
	enabled = prompt_yes_no('Would you like to configure the print service?' + '\n', preset.enabled if preset else False)
	return preset if enabled is None else PrintServiceConfiguration(enabled)


def select_flatpak(preset: FlatpakConfiguration | None) -> FlatpakConfiguration | None:
	enabled = prompt_yes_no('Install flatpak with the flathub remote and a portal fallback?' + '\n', preset.enabled if preset else False)
	return preset if enabled is None else FlatpakConfiguration(enabled)


def select_media_codecs(preset: MediaCodecsConfiguration | None) -> MediaCodecsConfiguration | None:
	enabled = prompt_yes_no('Install the media codec set (gstreamer bad/ugly/libav, dvd, raw)?' + '\n', preset.enabled if preset else False)
	return preset if enabled is None else MediaCodecsConfiguration(enabled)


def select_audio(preset: AudioConfiguration | None = None) -> AudioConfiguration | None:
	items = [MenuItem(a.value, value=a) for a in Audio]
	items.append(MenuItem(text='None', value=None))

	choice = prompt_choice(items, preset.audio if preset else None, frame='Audio')
	return AudioConfiguration(choice) if choice else None


def select_firewall(preset: FirewallConfiguration | None = None) -> FirewallConfiguration | None:
	choice = prompt_choice(MenuItemGroup.from_enum(Firewall), preset.firewall if preset else None, frame='Firewall', allow_reset=True)
	return FirewallConfiguration(choice) if choice else None


def select_management(preset: ManagementConfiguration | None = None) -> ManagementConfiguration | None:
	options = [m for m in Management if not (m == Management.REFLECTOR and SysInfo.arch() != 'x86_64')]
	items = [MenuItem(m.value, value=m) for m in options]
	group = MenuItemGroup(items)

	header = 'Would you like to install management tools?' + '\n'

	if preset:
		group.set_selected_by_value(preset.tools)

	result = SelectMenu[Management](
		group,
		header=header,
		allow_skip=True,
		alignment=Alignment.CENTER,
		allow_reset=True,
		frame=FrameProperties.min('Management'),
		multi=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return ManagementConfiguration(tools=result.get_values())
		case ResultType.Reset:
			return None


def select_monitor(preset: MonitorConfiguration | None = None) -> MonitorConfiguration | None:
	choice = prompt_choice(MenuItemGroup.from_enum(Monitor), preset.monitor if preset else None, frame='Monitor', allow_reset=True)
	return MonitorConfiguration(choice) if choice else None


def select_editor(preset: EditorConfiguration | None = None) -> EditorConfiguration | None:
	header = 'Set an editor globally through /etc/environment?' + '\n'
	choice = prompt_choice(MenuItemGroup.from_enum(Editor), preset.editor if preset else None, header=header, frame='Editor', allow_reset=True)
	return EditorConfiguration(choice) if choice else None


def select_terminal(preset: TerminalConfiguration | None = None) -> TerminalConfiguration | None:
	header = 'Set a terminal globally through /etc/environment?' + '\n'
	header += 'Window manager profiles bind it too (foot is Wayland only)' + '\n'
	choice = prompt_choice(MenuItemGroup.from_enum(Terminal), preset.terminal if preset else None, header=header, frame='Terminal', allow_reset=True)
	return TerminalConfiguration(choice) if choice else None


def select_security(preset: SecurityConfiguration | None = None) -> SecurityConfiguration | None:
	items = [MenuItem(s.value, value=s) for s in Security]
	group = MenuItemGroup(items)

	header = 'Would you like to install security tools?' + '\n'

	if preset:
		group.set_selected_by_value(preset.tools)

	result = SelectMenu[Security](
		group,
		header=header,
		allow_skip=True,
		alignment=Alignment.CENTER,
		allow_reset=True,
		frame=FrameProperties.min('Security'),
		multi=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return SecurityConfiguration(tools=result.get_values())
		case ResultType.Reset:
			return None


def select_development(preset: DevelopmentConfiguration | None = None) -> DevelopmentConfiguration | None:
	config = DevelopmentMenu(preset).run()
	if config.language_config is None and config.devtool_config is None:
		return None
	return config


def select_languages(preset: LanguageConfiguration | None = None) -> LanguageConfiguration | None:
	items = [MenuItem(lang.value, value=lang) for lang in Language]
	group = MenuItemGroup(items)

	header = 'Would you like to install language toolchains?' + '\n'

	if preset:
		group.set_selected_by_value(preset.tools)

	result = SelectMenu[Language](
		group,
		header=header,
		allow_skip=True,
		alignment=Alignment.CENTER,
		allow_reset=True,
		frame=FrameProperties.min('Languages'),
		multi=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return LanguageConfiguration(tools=result.get_values())
		case ResultType.Reset:
			return None


def select_devtools(preset: DevToolConfiguration | None = None) -> DevToolConfiguration | None:
	items = [MenuItem(tool.value, value=tool) for tool in DevTool]
	group = MenuItemGroup(items)

	header = 'Would you like to install build & debug tools?' + '\n'

	if preset:
		group.set_selected_by_value(preset.tools)

	result = SelectMenu[DevTool](
		group,
		header=header,
		allow_skip=True,
		alignment=Alignment.CENTER,
		allow_reset=True,
		frame=FrameProperties.min('Build & Debug'),
		multi=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return DevToolConfiguration(tools=result.get_values())
		case ResultType.Reset:
			return None
