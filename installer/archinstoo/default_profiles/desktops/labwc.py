from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import ProfileType, SeatAccess, seat_services
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class LabwcProfile(WaylandProfile):
	needs_terminal = True

	def __init__(self) -> None:
		super().__init__(
			'labwc',
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
			'labwc',
			*additional,
			'xdg-desktop-portal-wlr',  # labwc-portals.conf: default=wlr; labwc pulls no backend
		]

	@override
	def install(self, install_session: Installer) -> None:
		super().install(install_session)

		# xdg-desktop-portal-wlr only starts once the systemd user session knows the
		# compositor; sway ships a drop-in for this, labwc leaves it to autostart
		autostart = install_session.target / 'etc/xdg/labwc/autostart'
		autostart.parent.mkdir(parents=True, exist_ok=True)
		line = 'systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP && '
		line += 'dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP\n'
		existing = autostart.read_text() if autostart.is_file() else ''
		if 'import-environment' not in existing:
			autostart.write_text(existing + line)
			autostart.chmod(0o755)

	@property
	@override
	def services(self) -> list[str]:
		return seat_services(self.custom_settings.get('seat_access'))

	def _select_seat_access(self) -> None:
		# need to activate seat service and add to seat group
		header = 'labwc needs access to your seat (collection of hardware devices i.e. keyboard, mouse, etc)'
		header += '\n' + 'Choose an option to give labwc access to your hardware' + '\n'

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
