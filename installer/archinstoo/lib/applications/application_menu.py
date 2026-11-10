import textwrap
from typing import override

from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.menu.abstract_menu import AbstractSubMenu
from archinstoo.lib.models.applications import (
	EXPERIMENTAL_CPU_SCHEDULERS,
	ApplicationConfiguration,
	Audio,
	AudioConfiguration,
	BluetoothConfiguration,
	CPUScheduler,
	CPUSchedulerConfiguration,
	Editor,
	EditorConfiguration,
	Firewall,
	FirewallConfiguration,
	FlatpakConfiguration,
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
		return [
			text
			for entry in self._item_group.items
			if entry.preview_action
			and (text := entry.preview_action(entry))
		]

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
				preview_action=self._prev,
				key='bluetooth_config',
			),
			MenuItem(
				text='Thunderbolt',
				action=select_thunderbolt,
				value=self._app_config.thunderbolt_config,
				preview_action=self._prev,
				enabled=SysInfo.has_thunderbolt(),
				key='thunderbolt_config',
			),
			MenuItem(
				text='Audio',
				action=select_audio,
				preview_action=self._prev,
				key='audio_config',
			),
			MenuItem(
				text='Print service',
				action=select_print_service,
				preview_action=self._prev,
				key='print_service_config',
			),
			MenuItem(
				text='Media codecs',
				action=select_media_codecs,
				preview_action=self._prev,
				key='media_codecs_config',
			),
			MenuItem(
				text='Flatpak',
				action=select_flatpak,
				preview_action=self._prev,
				key='flatpak_config',
			),
			MenuItem(
				text='Power management',
				action=select_power_management,
				preview_action=self._prev,
				key='power_management_config',
			),
			MenuItem(
				text='Firewall',
				action=select_firewall,
				preview_action=self._prev,
				key='firewall_config',
			),
			MenuItem(
				text='Management',
				action=select_management,
				preview_action=self._prev,
				key='management_config',
			),
			MenuItem(
				text='Monitor',
				action=select_monitor,
				preview_action=self._prev,
				key='monitor_config',
			),
			MenuItem(
				text='Editor',
				action=select_editor,
				preview_action=self._prev,
				key='editor_config',
			),
			MenuItem(
				text='Terminal',
				action=select_terminal,
				preview_action=self._prev,
				key='terminal_config',
			),
			MenuItem(
				text='Security',
				action=select_security,
				preview_action=self._prev,
				key='security_config',
			),
		]

		# sched_ext is opt-in; only surfaced with --advanced
		if self._advanced:
			items.append(
				MenuItem(
					text='CPU scheduler',
					action=select_cpu_scheduler,
					preview_action=self._prev,
					key='cpu_scheduler_config',
				),
			)

		return items

	def _prev(self, item: MenuItem) -> str | None:
		# every category holds one field (models/applications._Category): a
		# flag, a choice or a list of them, shown under the item's own label
		if item.value is None:
			return None

		(value,) = vars(item.value).values()
		if isinstance(value, bool):
			return _enabled_text(item.text, value)
		if isinstance(value, list):
			return f'{item.text}: {", ".join(v.value for v in value)}'
		return f'{item.text}: {value.value}'


def select_power_management(
	preset: PowerManagementConfiguration | None = None,
) -> PowerManagementConfiguration | None:
	choice = prompt_choice(
		MenuItemGroup.from_enum(PowerManagement),
		preset.power_management if preset else None,
		frame='Power management',
		allow_reset=True,
	)
	return PowerManagementConfiguration(choice) if choice else None


def select_cpu_scheduler(
	preset: CPUSchedulerConfiguration | None = None,
) -> CPUSchedulerConfiguration | None:
	items = [MenuItem(text='Stable', read_only=True)]
	items += [
		MenuItem(text=f'  {s.value}', value=s)
		for s in CPUScheduler
		if s not in EXPERIMENTAL_CPU_SCHEDULERS
	]
	items.append(MenuItem(text='Experimental', read_only=True))
	items += [
		MenuItem(text=f'  {s.value}', value=s)
		for s in CPUScheduler
		if s in EXPERIMENTAL_CPU_SCHEDULERS
	]

	choice = prompt_choice(
		items,
		preset.scheduler if preset else None,
		frame='CPU scheduler',
		allow_reset=True,
	)
	return CPUSchedulerConfiguration(choice) if choice else None


def _enabled_text(label: str, enabled: bool) -> str:
	return f'{label}: {"Enabled" if enabled else "Disabled"}'


def select_bluetooth(
	preset: BluetoothConfiguration | None,
) -> BluetoothConfiguration | None:
	enabled = prompt_yes_no(
		'Would you like to configure Bluetooth?\n',
		preset.enabled if preset else False,
	)
	return preset if enabled is None else BluetoothConfiguration(enabled)


def select_thunderbolt(
	preset: ThunderboltConfiguration | None,
) -> ThunderboltConfiguration | None:
	enabled = prompt_yes_no(
		textwrap.dedent("""\
			Would you like to configure Thunderbolt device authorization
			(bolt)? New devices are auto-enrolled when the desktop asks or
			IOMMU DMA protection is on, otherwise once with:
			boltctl enroll --policy auto <uuid>
		"""),
		preset.enabled if preset else False,
	)
	return preset if enabled is None else ThunderboltConfiguration(enabled)


def select_print_service(
	preset: PrintServiceConfiguration | None,
) -> PrintServiceConfiguration | None:
	enabled = prompt_yes_no(
		'Would you like to configure the print service?\n',
		preset.enabled if preset else False,
	)
	return preset if enabled is None else PrintServiceConfiguration(enabled)


def select_flatpak(preset: FlatpakConfiguration | None) -> FlatpakConfiguration | None:
	enabled = prompt_yes_no(
		'Install flatpak with the flathub remote and a portal fallback?\n',
		preset.enabled if preset else False,
	)
	return preset if enabled is None else FlatpakConfiguration(enabled)


def select_media_codecs(
	preset: MediaCodecsConfiguration | None,
) -> MediaCodecsConfiguration | None:
	enabled = prompt_yes_no(
		'Install the media codec set (gstreamer bad/ugly/libav, dvd, raw)?\n',
		preset.enabled if preset else False,
	)
	return preset if enabled is None else MediaCodecsConfiguration(enabled)


def select_audio(preset: AudioConfiguration | None = None) -> AudioConfiguration | None:
	items = [MenuItem(a.value, value=a) for a in Audio]
	items.append(MenuItem(text='None', value=None))

	choice = prompt_choice(items, preset.audio if preset else None, frame='Audio')
	return AudioConfiguration(choice) if choice else None


def select_firewall(
	preset: FirewallConfiguration | None = None,
) -> FirewallConfiguration | None:
	choice = prompt_choice(
		MenuItemGroup.from_enum(Firewall),
		preset.firewall if preset else None,
		frame='Firewall',
		allow_reset=True,
	)
	return FirewallConfiguration(choice) if choice else None


def select_management(
	preset: ManagementConfiguration | None = None,
) -> ManagementConfiguration | None:
	options = [
		m
		for m in Management
		if not (m == Management.REFLECTOR and SysInfo.arch() != 'x86_64')
	]
	items = [MenuItem(m.value, value=m) for m in options]
	group = MenuItemGroup(items)

	header = 'Would you like to install management tools?\n'

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


def select_monitor(
	preset: MonitorConfiguration | None = None,
) -> MonitorConfiguration | None:
	choice = prompt_choice(
		MenuItemGroup.from_enum(Monitor),
		preset.monitor if preset else None,
		frame='Monitor',
		allow_reset=True,
	)
	return MonitorConfiguration(choice) if choice else None


def select_editor(
	preset: EditorConfiguration | None = None,
) -> EditorConfiguration | None:
	header = 'Set an editor globally through /etc/environment?\n'
	choice = prompt_choice(
		MenuItemGroup.from_enum(Editor),
		preset.editor if preset else None,
		header=header,
		frame='Editor',
		allow_reset=True,
	)
	return EditorConfiguration(choice) if choice else None


def select_terminal(
	preset: TerminalConfiguration | None = None,
) -> TerminalConfiguration | None:
	header = 'Set a terminal globally through /etc/environment?\n'
	header += 'Window manager profiles bind it too (foot is Wayland only)\n'
	choice = prompt_choice(
		MenuItemGroup.from_enum(Terminal),
		preset.terminal if preset else None,
		header=header,
		frame='Terminal',
		allow_reset=True,
	)
	return TerminalConfiguration(choice) if choice else None


def select_security(
	preset: SecurityConfiguration | None = None,
) -> SecurityConfiguration | None:
	items = [MenuItem(s.value, value=s) for s in Security]
	group = MenuItemGroup(items)

	header = 'Would you like to install security tools?\n'

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
