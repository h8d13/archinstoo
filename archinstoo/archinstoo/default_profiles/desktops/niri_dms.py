import shutil
from pathlib import Path
from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.desktops import SeatAccess
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


_TERMINAL = 'alacritty'
_ASSETS_DIR = Path(__file__).parent / 'niri_dms_assets'


class NiriDmsProfile(WaylandProfile):
	def __init__(self) -> None:
		super().__init__(
			'niri - DankMaterialShell',
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
			'niri',
			'dms-shell-niri',
			'xdg-desktop-portal-gnome',
			'xorg-xwayland',
			'matugen',
			'cava',
			'kimageformats',
			_TERMINAL,
		] + additional

	@property
	@override
	def services(self) -> list[str]:
		pref = self.custom_settings.get('seat_access')
		return [pref] if isinstance(pref, str) else []

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		# dms ships its own greetd-based greeter; session-transparent, seatd-safe
		return GreeterType.GreetdDms

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		super().provision(install_session, users)

		binds = (_ASSETS_DIR / 'dms/binds.kdl').read_text().replace('{{TERMINAL_COMMAND}}', _TERMINAL)

		for user in users:
			home = install_session.target / 'home' / user.username
			niri_dir = home / '.config/niri'
			dms_dir = niri_dir / 'dms'
			dms_dir.mkdir(parents=True, exist_ok=True)

			shutil.copy(_ASSETS_DIR / 'niri.kdl', niri_dir / 'config.kdl')
			for name in ('colors.kdl', 'layout.kdl', 'alttab.kdl', 'outputs.kdl', 'cursor.kdl'):
				shutil.copy(_ASSETS_DIR / 'dms' / name, dms_dir / name)
			(dms_dir / 'binds.kdl').write_text(binds)

			niri_unit_dropin = home / '.config/systemd/user/niri.service.d'
			niri_unit_dropin.mkdir(parents=True, exist_ok=True)
			(niri_unit_dropin / 'dms.conf').write_text('[Unit]\nWants=dms.service\n')

			install_session.arch_chroot(['chown', '-R', f'{user.username}:{user.username}', f'/home/{user.username}/.config'])

	def _select_seat_access(self) -> None:
		header = 'Niri needs access to your seat (collection of hardware devices i.e. keyboard, mouse, etc)'
		header += '\n' + 'Choose an option to give Niri access to your hardware' + '\n'

		items = [MenuItem(s.value, value=s) for s in SeatAccess]
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
