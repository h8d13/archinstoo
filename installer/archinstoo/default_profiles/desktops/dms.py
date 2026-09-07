from typing import TYPE_CHECKING, ClassVar, override

from archinstoo.default_profiles.desktops import SeatAccess, seat_services, swap_terminal
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.output import warn
from archinstoo.lib.profile.base import GreeterType, ProfileType
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties

if TYPE_CHECKING:
	from pathlib import Path

	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class DmsProfile(WaylandProfile):
	needs_terminal = True

	# the one file `dms setup headless` leaves a terminal in, per compositor
	binds_paths: ClassVar[dict[str, str]] = {
		'niri': '.config/niri/dms/binds.kdl',
		'hyprland': '.config/hypr/dms/binds.lua',
	}

	# dms-shell-<compositor> pulls dms-shell (quickshell, dgop)
	compositor_packages: ClassVar[dict[str, list[str]]] = {
		'niri': ['niri', 'dms-shell-niri', 'xdg-desktop-portal-gnome', 'xorg-xwayland'],
		# uwsm backs the "Hyprland (uwsm)" session entry the hyprland package ships
		'hyprland': ['hyprland', 'dms-shell-hyprland', 'xdg-desktop-portal-hyprland', 'uwsm'],
	}

	# dms-shell 1.6.0 embedded the UI in the dms binary and dropped
	# /usr/share/quickshell/dms, which is where its own greetd greeter lived;
	# the launcher moved to a standalone AUR package. no repo greeter left to
	# name, so fall back like the plain hyprland profile
	_default_greeter_non_seatd = GreeterType.Sddm

	def __init__(self) -> None:
		super().__init__(
			'dms',
			ProfileType.WindowMgr,
		)

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

		compositor_pkgs = [p for comp in self.compositors for p in self.compositor_packages[comp]]

		return [
			*compositor_pkgs,
			'matugen',
			'cava',
			'kimageformats',
			# dms defaults: Inter Variable + Fira Code. the shell bundles both
			# privately, but doctor <= 1.5.3 only checks fontconfig, and the
			# terminal needs a real mono font anyway
			'inter-font',
			'ttf-fira-code',
			*additional,
		]

	@property
	@override
	def services(self) -> list[str]:
		return seat_services(self.custom_settings.get('seat_access'))

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		super().provision(install_session, users)

		# dms.service (WantedBy=graphical-session.target) autostarts the shell in
		# any session that activates the target: niri natively, hyprland via the
		# hyprland-session.target the setup below deploys
		install_session.arch_chroot(['systemctl', '--global', 'enable', 'dms.service'])

		# `dms setup headless` writes the compositor config, the dms/ overrides
		# and (for hyprland) ~/.config/systemd/user/hyprland-session.target.
		# it has to run as the user: everything lands under their $HOME
		for user in users:
			for comp in self.compositors:
				install_session.arch_chroot(
					['dms', 'setup', 'headless', '--compositor', comp, '--skip-existing'],
					run_as=user.username,
				)

				self._repoint_terminal(install_session.target / 'home' / user.username, comp)

			install_session.chown_tree(user.username, f'/home/{user.username}/.config')

	def _repoint_terminal(self, home: Path, compositor: str) -> None:
		# --terminal takes three of the seven terminals we offer and deploys a
		# config for it besides, so let dms ship its own default and move the
		# keybind afterwards
		binds = home / self.binds_paths[compositor]

		if not binds.is_file():
			warn(f'{binds} missing, leaving the terminal keybind to dms')
			return

		binds.write_text(swap_terminal(binds.read_text(), 'ghostty', binds))

	def _select_compositors(self) -> None:
		header = 'DankMaterialShell runs on top of a Wayland compositor' + '\n'
		header += 'Choose one or more to install' + '\n'

		items = [MenuItem(c, value=c) for c in self.compositor_packages]
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
		self._select_compositors()
		self._select_seat_access()
