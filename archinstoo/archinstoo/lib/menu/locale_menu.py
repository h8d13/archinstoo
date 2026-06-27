from typing import override

from archinstoo.lib.localization.utils import (
	list_console_fonts,
	list_keyboard_languages,
	list_locales,
	list_x11_keyboard_languages,
	list_x11_keyboard_models,
	list_x11_keyboard_options,
	list_x11_keyboard_variants,
	set_kb_layout,
)
from archinstoo.lib.menu.abstract_menu import AbstractSubMenu
from archinstoo.lib.models.locale import LocaleConfiguration
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties


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
				text='Keyboard layout',
				action=self._select_kb_layout,
				value=self._locale_conf.kb_layout,
				preview_action=self._prev_locale,
				key='kb_layout',
			),
			MenuItem(
				text='Keyboard layout (X11/Wayland)',
				action=self._select_xkb_layout,
				value=self._locale_conf.xkb_layout,
				preview_action=self._prev_locale,
				key='xkb_layout',
			),
			MenuItem(
				text='Layout variant (X11/Wayland)',
				action=self._select_xkb_variant,
				value=self._locale_conf.xkb_variant,
				preview_action=self._prev_locale,
				key='xkb_variant',
				# only shown once a graphical layout is chosen
				enabled=bool(self._locale_conf.xkb_layout),
			),
			MenuItem(
				text='Keyboard model (X11/Wayland)',
				action=select_xkb_model,
				value=self._locale_conf.xkb_model,
				preview_action=self._prev_locale,
				key='xkb_model',
			),
			MenuItem(
				text='XKB options (X11/Wayland)',
				action=select_xkb_options,
				value=self._locale_conf.xkb_options,
				preview_action=self._prev_locale,
				key='xkb_options',
			),
			MenuItem(
				text='Locale language',
				action=select_locale_lang,
				value=self._locale_conf.sys_lang,
				preview_action=self._prev_locale,
				key='sys_lang',
			),
			MenuItem(
				text='Locale encoding',
				action=select_locale_enc,
				value=self._locale_conf.sys_enc,
				preview_action=self._prev_locale,
				key='sys_enc',
			),
			MenuItem(
				text='Console font',
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
		# xkb fields default to '' (graphical layout left unset)
		xkb_layout = self._menu_item_group.find_by_key('xkb_layout').value or ''
		xkb_model = self._menu_item_group.find_by_key('xkb_model').value or ''
		xkb_variant = self._menu_item_group.find_by_key('xkb_variant').value or ''
		xkb_options = self._menu_item_group.find_by_key('xkb_options').value or ''

		temp_locale = LocaleConfiguration(
			kb_layout,
			sys_lang,
			sys_enc,
			console_font,
			xkb_layout=xkb_layout,
			xkb_model=xkb_model,
			xkb_variant=xkb_variant,
			xkb_options=xkb_options,
		)
		return temp_locale.preview()

	@override
	def run(
		self,
		additional_title: str | None = None,
	) -> LocaleConfiguration:
		super().run(additional_title=additional_title)
		# If reset, return defaults instead of config with None fields
		# Note: kb_layout can be None at runtime after reset despite type annotation
		if getattr(self._locale_conf, 'kb_layout', None) is None:
			return LocaleConfiguration.default()
		return self._locale_conf

	def _select_kb_layout(self, preset: str | None) -> str | None:
		if kb_lang := select_kb_layout(preset):
			set_kb_layout(kb_lang)
		return kb_lang

	def _select_xkb_layout(self, preset: str | None) -> str | None:
		layout = select_xkb_layout(preset)

		# variant is layout-scoped: reveal it only once a layout is set, and
		# drop a stale variant when the layout is cleared or changed
		variant_item = self._menu_item_group.find_by_key('xkb_variant')
		if not layout:
			variant_item.enabled = False
			variant_item.value = ''
			self._locale_conf.xkb_variant = ''
		else:
			variant_item.enabled = True
			if layout != preset:
				variant_item.value = ''
				self._locale_conf.xkb_variant = ''

		return layout

	def _select_xkb_variant(self, preset: str | None) -> str | None:
		# variants are scoped to the chosen graphical layout
		layout = self._menu_item_group.find_by_key('xkb_layout').value
		return select_xkb_variant(layout, preset)


def select_locale_lang(preset: str | None = None) -> str | None:
	locales = list_locales()
	locale_lang = {locale.split()[0] for locale in locales}

	items = [MenuItem(ll, value=ll) for ll in locale_lang]
	group = MenuItemGroup(items, sort_items=True)
	group.set_focus_by_value(preset)

	result = SelectMenu[str](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min('Locale language'),
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
		frame=FrameProperties.min('Locale encoding'),
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
		frame=FrameProperties.min('Console font'),
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
	# Select keyboard layout
	#
	# :return: The keyboard layout shortcut for the selected layout
	# :rtype: str
	kb_lang = list_keyboard_languages()
	# sort alphabetically and then by length
	sorted_kb_lang = sorted(kb_lang, key=lambda x: (len(x), x))

	items = [MenuItem(lang, value=lang) for lang in sorted_kb_lang]
	group = MenuItemGroup(items, sort_items=False)
	group.set_focus_by_value(preset)

	result = SelectMenu[str](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min('Keyboard layout'),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled return type')


def _select_xkb_single(title: str, values: list[str], preset: str | None) -> str | None:
	# single-select with a leading sentinel so the choice can be cleared back
	# to '' (graphical layout unset). Empty source list => nothing to pick.
	if not values:
		return preset

	items = [MenuItem('(none)', value=''), *(MenuItem(v, value=v) for v in values)]
	group = MenuItemGroup(items, sort_items=False)
	group.set_focus_by_value(preset or '')

	result = SelectMenu[str](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(title),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Skip:
			return preset
		case _:
			raise ValueError('Unhandled return type')


def select_xkb_layout(preset: str | None = None) -> str | None:
	layouts = sorted(list_x11_keyboard_languages())
	return _select_xkb_single('Keyboard layout (X11/Wayland)', layouts, preset)


def select_xkb_model(preset: str | None = None) -> str | None:
	return _select_xkb_single('Keyboard model', list_x11_keyboard_models(), preset)


def select_xkb_variant(layout: str | None, preset: str | None = None) -> str | None:
	return _select_xkb_single('Layout variant', list_x11_keyboard_variants(layout or ''), preset)


def select_xkb_options(preset: str | None = None) -> str | None:
	# comma-separated list (matches XkbOptions / XKB_DEFAULT_OPTIONS)
	options = list_x11_keyboard_options()
	if not options:
		return preset

	items = [MenuItem(o, value=o) for o in options]
	group = MenuItemGroup(items, sort_items=False)
	group.set_selected_by_value(preset.split(',') if preset else [])

	result = SelectMenu[str](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min('XKB options'),
		allow_reset=True,
		allow_skip=True,
		multi=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return ''
		case ResultType.Selection:
			return ','.join(result.get_values())
		case _:
			raise ValueError('Unhandled return type')
