from typing import override

from archinstoo.lib.menu.abstract_menu import AbstractSubMenu
from archinstoo.lib.models.locale import LocaleConfiguration
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties

from .utils import list_console_fonts, list_keyboard_languages, list_locales, set_kb_layout


class LocaleMenu(AbstractSubMenu[LocaleConfiguration]):
	def __init__(
		self,
		locale_conf: LocaleConfiguration,
	):
		self._locale_conf = locale_conf
		menu_options = self._define_menu_options()

		self._item_group = MenuItemGroup(menu_options, sort_items=False, checkmarks=True)
		super().__init__(
			self._item_group,
			config=self._locale_conf,
			allow_reset=True,
		)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=tr('Keyboard layout'),
				action=self._select_kb_layout,
				value=self._locale_conf.kb_layout,
				preview_action=self._prev_locale,
				key='kb_layout',
			),
			MenuItem(
				text=tr('Locale language'),
				action=select_locale_lang,
				value=self._locale_conf.sys_lang,
				preview_action=self._prev_locale,
				key='sys_lang',
			),
			MenuItem(
				text=tr('Locale encoding'),
				action=select_locale_enc,
				value=self._locale_conf.sys_enc,
				preview_action=self._prev_locale,
				key='sys_enc',
			),
			MenuItem(
				text=tr('Console font'),
				action=select_console_font,
				value=self._locale_conf.console_font,
				preview_action=self._prev_locale,
				key='console_font',
			),
		]

	def _prev_locale(self, item: MenuItem) -> str:
		default = LocaleConfiguration.default()
		kb_layout = self._menu_item_group.find_by_key('kb_layout').value or default.kb_layout
		sys_lang = self._menu_item_group.find_by_key('sys_lang').value or default.sys_lang
		sys_enc = self._menu_item_group.find_by_key('sys_enc').value or default.sys_enc
		console_font = self._menu_item_group.find_by_key('console_font').value or default.console_font

		temp_locale = LocaleConfiguration(kb_layout, sys_lang, sys_enc, console_font)
		return temp_locale.preview()

	@override
	def run(
		self,
		additional_title: str | None = None,
	) -> LocaleConfiguration:
		super().run(additional_title=additional_title)
		return self._locale_conf

	def _select_kb_layout(self, preset: str | None) -> str | None:
		if kb_lang := select_kb_layout(preset):
			set_kb_layout(kb_lang)
		return kb_lang


def select_locale_lang(preset: str | None = None) -> str | None:
	locales = list_locales()
	locale_lang = {locale.split()[0] for locale in locales}

	items = [MenuItem(ll, value=ll) for ll in locale_lang]
	group = MenuItemGroup(items, sort_items=True)
	group.set_focus_by_value(preset)

	result = SelectMenu[str](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Locale language')),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled return type')


def select_locale_enc(preset: str | None = None) -> str | None:
	locales = list_locales()
	locale_enc = {locale.split()[1] for locale in locales}

	items = [MenuItem(le, value=le) for le in locale_enc]
	group = MenuItemGroup(items, sort_items=True)
	group.set_focus_by_value(preset)

	result = SelectMenu[str](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Locale encoding')),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled return type')


def select_console_font(preset: str | None = None) -> str | None:
	fonts = list_console_fonts()

	items = [MenuItem(f, value=f) for f in fonts]
	group = MenuItemGroup(items, sort_items=False)
	group.set_focus_by_value(preset)

	result = SelectMenu[str](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Console font')),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled return type')


def select_kb_layout(preset: str | None = None) -> str | None:
	"""
	Select keyboard layout

	:return: The keyboard layout shortcut for the selected layout
	:rtype: str
	"""

	kb_lang = list_keyboard_languages()
	# sort alphabetically and then by length
	sorted_kb_lang = sorted(kb_lang, key=lambda x: (len(x), x))

	items = [MenuItem(lang, value=lang) for lang in sorted_kb_lang]
	group = MenuItemGroup(items, sort_items=False)
	group.set_focus_by_value(preset)

	result = SelectMenu[str](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Keyboard layout')),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled return type')
