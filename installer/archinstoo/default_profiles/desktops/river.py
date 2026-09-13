from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.desktops import provision_terminal_config
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import ProfileType, SeatAccess, seat_services
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class RiverProfile(WaylandProfile):
	needs_terminal = True

	def __init__(self) -> None:
		super().__init__('river', ProfileType.WindowMgr)

		self.custom_settings = {'seat_access': None}

	@property
	@override
	def packages(self) -> list[str]:
		additional: list[str] = []
		seat = self.custom_settings.get('seat_access')
		if isinstance(seat, str):
			additional = [seat]

		# `river` in extra is the 0.4 rewrite: compositor only, the window
		# manager is a separate client and none is packaged. river-classic
		# is the 0.3 line with riverctl/rivertile, the one that runs standalone
		return [
			'xdg-desktop-portal-wlr',
			'river-classic',
			# the shipped init binds the media keys to these three; eject is
			# util-linux. nothing else in it spawns a program besides the terminal
			'pamixer',
			'playerctl',
			'brightnessctl',
			*additional,
		]

	@property
	@override
	def services(self) -> list[str]:
		return seat_services(self.custom_settings.get('seat_access'))

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		super().provision(install_session, users)

		# river reads ~/.config/river/init and nothing else (no /etc fallback).
		# the example binds Super+Shift+Return to a hardcoded foot
		provision_terminal_config(
			install_session,
			users,
			install_session.target / 'usr/share/river-classic/example/init',
			'river/init',
			'foot',
			executable=True,
		)

	def _select_seat_access(self) -> None:
		# need to activate seat service and add to seat group
		header = 'River needs access to your seat (collection of hardware devices i.e. keyboard, mouse, etc)'
		header += '\n' + 'Choose an option to give River access to your hardware' + '\n'

		items = [MenuItem(s.label, value=s) for s in SeatAccess]
		group = MenuItemGroup(items, sort_items=True)

		default = self.custom_settings.get('seat_access', None)
		group.set_default_by_value(default)

		result = SelectMenu[SeatAccess](
			group,
			header=header,
			allow_skip=False,
			frame=FrameProperties.min('Seat access'),
			alignment=Alignment.CENTER,
		).run()

		if result.type_ == ResultType.Selection:
			self.custom_settings['seat_access'] = result.get_value().value

	@override
	def do_on_select(self) -> None:
		self._select_seat_access()
