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

_TERMINAL = 'kitty'
_ASSETS_DIR = Path(__file__).parent / 'noctalia_assets'

# noctalia v5: native wayland shell (bar, launcher, lock, notifications,
# clipboard, polkit agent), no qt/gtk deps; compositor is a free choice
_COMPOSITOR_PACKAGES = {
	'niri': ['niri', 'xdg-desktop-portal-gnome', 'xorg-xwayland'],
	# uwsm backs the "Hyprland (uwsm)" session entry the hyprland package ships
	'hyprland': ['hyprland', 'xdg-desktop-portal-hyprland', 'uwsm'],
	'sway': ['sway', 'xdg-desktop-portal-wlr', 'xorg-xwayland'],
	'labwc': ['labwc', 'xdg-desktop-portal-wlr', 'xorg-xwayland'],
}

# compositor -> config dir under ~/.config; every file in the matching
# noctalia_assets/<compositor>/ dir is provisioned into it
_COMPOSITOR_CONFIG_DIRS = {
	'niri': 'niri',
	'hyprland': 'hypr',
	'sway': 'sway',
	'labwc': 'labwc',
}


class NoctaliaProfile(WaylandProfile):
	# noctalia-greeter (greetd) is not packaged in the arch repos yet;
	# fall back to sddm like the plain hyprland profile
	_default_greeter_non_seatd = GreeterType.Sddm

	def __init__(self) -> None:
		super().__init__('noctalia', ProfileType.WindowMgr)

		self.custom_settings = {'noctalia_compositor': ['niri'], 'seat_access': None}

	@property
	def compositors(self) -> list[str]:
		comp = self.custom_settings.get('noctalia_compositor')
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
			'noctalia',
			# noctalia resolves fonts via fontconfig (sans-serif default);
			# bare installs ship none, so seed one sans + one mono
			'inter-font',
			'ttf-jetbrains-mono-nerd',
			_TERMINAL,
		] + additional

	@property
	@override
	def services(self) -> list[str]:
		pref = self.custom_settings.get('seat_access')
		return [pref] if isinstance(pref, str) else []

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		super().provision(install_session, users)

		# noctalia starts via the compositor's autostart hook; only the
		# compositor config is provisioned, the shell configures itself
		for user in users:
			config_dir = install_session.target / 'home' / user.username / '.config'

			for comp in self.compositors:
				dest_dir = config_dir / _COMPOSITOR_CONFIG_DIRS[comp]
				dest_dir.mkdir(parents=True, exist_ok=True)

				for asset in sorted((_ASSETS_DIR / comp).iterdir()):
					conf = asset.read_text().replace('{{TERMINAL_COMMAND}}', _TERMINAL)
					(dest_dir / asset.name).write_text(conf)

			install_session.arch_chroot(['chown', '-R', f'{user.username}:{user.username}', f'/home/{user.username}/.config'])

	def _select_compositors(self) -> None:
		header = 'Noctalia runs on top of a Wayland compositor' + '\n'
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
			self.custom_settings['noctalia_compositor'] = values

	def _select_seat_access(self) -> None:
		# need to activate seat service and add to seat group
		header = 'Noctalia needs access to your seat (collection of hardware devices i.e. keyboard, mouse, etc)'
		header += '\n' + 'Choose an option to give Noctalia access to your hardware' + '\n'

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
