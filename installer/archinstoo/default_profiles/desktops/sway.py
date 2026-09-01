from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.desktops import SeatAccess, seat_services, swap_terminal, terminal_command
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.output import warn
from archinstoo.lib.profile.base import ProfileType
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class SwayProfile(WaylandProfile):
	def __init__(self) -> None:
		super().__init__(
			'sway',
			ProfileType.WindowMgr,
		)

		self.custom_settings = {'seat_access': None}

	@property
	@override
	def packages(self) -> list[str]:
		additional: list[str] = []
		seat = self.custom_settings.get('seat_access')
		if isinstance(seat, str):
			additional = [seat]

		return [
			'sway',
			'swaybg',
			'swaylock',
			'swayidle',
			'wmenu',
			'brightnessctl',
			'grim',
			'slurp',
			'pavucontrol',
			terminal_command(),
			'xorg-xwayland',
			*additional,
		]

	@property
	@override
	def services(self) -> list[str]:
		return seat_services(self.custom_settings.get('seat_access'))

	@override
	def install(self, install_session: Installer) -> None:
		super().install(install_session)

		# sway reads /etc/sway/config directly when the user has no
		# ~/.config/sway/config, and it ships `set $term foot`
		config = install_session.target / 'etc/sway/config'
		if not config.is_file():
			warn(f'{config} missing, leaving the sway terminal binding as shipped')
			return

		config.write_text(swap_terminal(config.read_text(), 'foot', config))

	def _select_seat_access(self) -> None:
		# need to activate seat service and add to seat group
		header = 'Sway needs access to your seat (collection of hardware devices i.e. keyboard, mouse, etc)'
		header += '\n' + 'Choose an option to give Sway access to your hardware' + '\n'

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
