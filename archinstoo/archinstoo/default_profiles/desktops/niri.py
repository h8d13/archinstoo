from typing import override

from archinstoo.default_profiles.desktops import SeatAccess
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import ProfileType
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties


class NiriProfile(WaylandProfile):
	def __init__(self) -> None:
		super().__init__(
			'Niri',
			ProfileType.WindowMgr,
		)

		self.custom_settings = {'seat_access': 'seatd'}

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'niri',
			'alacritty',
			'fuzzel',
			'mako',
			'xwayland-satellite',
			'waybar',
			'swaybg',
			'swayidle',
			'swaylock',
			'xdg-desktop-portal-gnome',
			'xdg-desktop-portal-gtk',
		]

	@property
	@override
	def services(self) -> list[str]:
		pref = self.custom_settings.get('seat_access')
		return [pref] if isinstance(pref, str) else []

	def _select_seat_access(self) -> None:
		header = tr('Niri needs access to your seat (collection of hardware devices i.e. keyboard, mouse, etc)')
		header += '\n' + tr('Choose an option to give Niri access to your hardware') + '\n'

		items = [MenuItem(s.value, value=s) for s in SeatAccess]
		group = MenuItemGroup(items, sort_items=True)

		default = self.custom_settings.get('seat_access', None)
		group.set_default_by_value(default)

		result = SelectMenu[SeatAccess](
			group,
			header=header,
			allow_skip=False,
			frame=FrameProperties.min(tr('Seat access')),
			alignment=Alignment.CENTER,
		).run()

		if result.type_ == ResultType.Selection:
			self.custom_settings['seat_access'] = result.get_value().value

	@override
	def do_on_select(self) -> None:
		self._select_seat_access()
