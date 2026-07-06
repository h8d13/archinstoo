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
_ASSETS_DIR = Path(__file__).parent / 'dms_assets'

# dms-shell-<compositor> pulls dms-shell (quickshell, dgop, greeter assets)
_COMPOSITOR_PACKAGES = {
	'niri': ['niri', 'dms-shell-niri', 'xdg-desktop-portal-gnome', 'xorg-xwayland'],
	'hyprland': ['hyprland', 'dms-shell-hyprland', 'xdg-desktop-portal-hyprland'],
}


class DmsProfile(WaylandProfile):
	def __init__(self) -> None:
		super().__init__(
			'dms',
			ProfileType.WindowMgr,
		)

		# dms_compositor also decides the greeter compositor (dms-greeter --command)
		self.custom_settings = {'dms_compositor': ['niri'], 'seat_access': None}

	@property
	def compositors(self) -> list[str]:
		comp = self.custom_settings.get('dms_compositor')
		if isinstance(comp, str):  # tolerate single value in hand-written configs
			return [comp]
		return comp if isinstance(comp, list) and comp else ['niri']

	@property
	@override
	def packages(self) -> list[str]:
		additional: list[str] = []
		seat = self.custom_settings.get('seat_access')
		if isinstance(seat, str):
			additional = [seat]

		compositor_pkgs = [p for comp in self.compositors for p in _COMPOSITOR_PACKAGES[comp]]

		return [
			*compositor_pkgs,
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

		for user in users:
			home = install_session.target / 'home' / user.username

			for comp in self.compositors:
				if comp == 'niri':
					self._provision_niri(home)
				else:
					self._provision_hyprland(home)

			install_session.arch_chroot(['chown', '-R', f'{user.username}:{user.username}', f'/home/{user.username}/.config'])

	def _provision_niri(self, home: Path) -> None:
		binds = (_ASSETS_DIR / 'niri/dms/binds.kdl').read_text().replace('{{TERMINAL_COMMAND}}', _TERMINAL)

		niri_dir = home / '.config/niri'
		dms_dir = niri_dir / 'dms'
		dms_dir.mkdir(parents=True, exist_ok=True)

		shutil.copy(_ASSETS_DIR / 'niri/niri.kdl', niri_dir / 'config.kdl')
		for name in ('colors.kdl', 'layout.kdl', 'alttab.kdl', 'outputs.kdl', 'cursor.kdl'):
			shutil.copy(_ASSETS_DIR / 'niri/dms' / name, dms_dir / name)
		(dms_dir / 'binds.kdl').write_text(binds)

		# niri runs as a systemd session; dms starts as its user service
		niri_unit_dropin = home / '.config/systemd/user/niri.service.d'
		niri_unit_dropin.mkdir(parents=True, exist_ok=True)
		(niri_unit_dropin / 'dms.conf').write_text('[Unit]\nWants=dms.service\n')

	def _provision_hyprland(self, home: Path) -> None:
		# no systemd session on hyprland; the config starts dms via exec-once
		conf = (_ASSETS_DIR / 'hyprland/hyprland.conf').read_text().replace('{{TERMINAL_COMMAND}}', _TERMINAL)

		hypr_dir = home / '.config/hypr'
		hypr_dir.mkdir(parents=True, exist_ok=True)
		(hypr_dir / 'hyprland.conf').write_text(conf)

	def _select_compositors(self) -> None:
		header = 'DankMaterialShell runs on top of a Wayland compositor' + '\n'
		header += 'Choose one or more to install' + '\n'

		items = [MenuItem(c, value=c) for c in _COMPOSITOR_PACKAGES]
		group = MenuItemGroup(items, sort_items=True)
		group.set_selected_by_value(self.compositors)

		result = SelectMenu[str](
			group,
			multi=True,
			header=header,
			allow_skip=False,
			frame=FrameProperties.min('Compositor'),
			alignment=Alignment.CENTER,
		).run()

		# empty multi-selection keeps the previous choice
		if result.type_ == ResultType.Selection and (values := result.get_values()):
			self.custom_settings['dms_compositor'] = values

	def _select_seat_access(self) -> None:
		header = 'DMS needs access to your seat (collection of hardware devices i.e. keyboard, mouse, etc)'
		header += '\n' + 'Choose an option to give DMS access to your hardware' + '\n'

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
		self._select_compositors()
		self._select_seat_access()
