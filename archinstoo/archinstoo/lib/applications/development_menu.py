from typing import override

from archinstoo.lib.menu.abstract_menu import AbstractSubMenu
from archinstoo.lib.models.application import (
	DevelopmentConfiguration,
	DevTool,
	DevToolConfiguration,
	Language,
	LanguageConfiguration,
)
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties


class DevelopmentMenu(AbstractSubMenu[DevelopmentConfiguration]):
	def __init__(
		self,
		preset: DevelopmentConfiguration | None = None,
	):
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
				text=tr('Languages'),
				action=select_languages,
				preview_action=self._prev_languages,
				key='language_config',
			),
			MenuItem(
				text=tr('Build & Debug'),
				action=select_devtools,
				preview_action=self._prev_devtools,
				key='devtool_config',
			),
		]

	def _prev_languages(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: LanguageConfiguration = item.value
			tools = ', '.join([t.value for t in config.tools])
			return f'{tr("Languages")}: {tools}'
		return None

	def _prev_devtools(self, item: MenuItem) -> str | None:
		if item.value is not None:
			config: DevToolConfiguration = item.value
			tools = ', '.join([t.value for t in config.tools])
			return f'{tr("Build & Debug")}: {tools}'
		return None


def select_languages(preset: LanguageConfiguration | None = None) -> LanguageConfiguration | None:
	items = [MenuItem(lang.value, value=lang) for lang in Language]
	group = MenuItemGroup(items)

	header = tr('Would you like to install language toolchains?') + '\n'

	if preset:
		group.set_selected_by_value(preset.tools)

	result = SelectMenu[Language](
		group,
		header=header,
		allow_skip=True,
		alignment=Alignment.CENTER,
		allow_reset=True,
		frame=FrameProperties.min(tr('Languages')),
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

	header = tr('Would you like to install build & debug tools?') + '\n'

	if preset:
		group.set_selected_by_value(preset.tools)

	result = SelectMenu[DevTool](
		group,
		header=header,
		allow_skip=True,
		alignment=Alignment.CENTER,
		allow_reset=True,
		frame=FrameProperties.min(tr('Build & Debug')),
		multi=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return DevToolConfiguration(tools=result.get_values())
		case ResultType.Reset:
			return None
