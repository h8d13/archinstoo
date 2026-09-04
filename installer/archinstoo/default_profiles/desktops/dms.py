import shutil
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from archinstoo.default_profiles.desktops import SeatAccess, seat_services, terminal_command
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


# canonical source (embedded in the dms binary, per AvengeMedia/DankMaterialShell#2851):
# https://github.com/AvengeMedia/DankMaterialShell/tree/master/core/internal/config/embedded
# dms/* files mirror it verbatim (niri outputs/cursor are deployed empty upstream;
# ours carry comment placeholders). hyprland.lua = embedded file plus the deployer's
# env lines in the DMS_STARTUP block (core/internal/config/hyprland_lua.go)
_ASSETS_DIR = Path(__file__).parent / 'dms_assets'


class DmsProfile(WaylandProfile):
	needs_terminal = True

	# dms-shell-<compositor> pulls dms-shell (quickshell, dgop, greeter assets)
	compositor_packages: ClassVar[dict[str, list[str]]] = {
		'niri': ['niri', 'dms-shell-niri', 'xdg-desktop-portal-gnome', 'xorg-xwayland'],
		# uwsm backs the "Hyprland (uwsm)" session entry the hyprland package ships
		'hyprland': ['hyprland', 'dms-shell-hyprland', 'xdg-desktop-portal-hyprland', 'uwsm'],
	}

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

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		# dms ships its own greetd-based greeter; session-transparent, seatd-safe
		return GreeterType.GreetdDms

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		super().provision(install_session, users)

		# dms.service (WantedBy=graphical-session.target) autostarts the shell in
		# any session that activates the target: niri natively, hyprland via the
		# session target below
		install_session.arch_chroot(['systemctl', '--global', 'enable', 'dms.service'])

		if 'hyprland' in self.compositors:
			# upstream's deployer writes this per-user; system-wide covers all.
			# starting it from hyprland.lua pulls graphical-session.target up
			# (BindsTo) even in sessions without a manager (plain "Hyprland"
			# entry), and is a no-op under uwsm where the target already runs
			target = install_session.target / 'etc/systemd/user/hyprland-session.target'
			target.parent.mkdir(parents=True, exist_ok=True)
			target.write_text(
				'[Unit]\n'
				'Description=Hyprland Session Target\n'
				'BindsTo=graphical-session.target\n'
				'Before=graphical-session.target\n'
				'Wants=graphical-session-pre.target\n'
				'After=graphical-session-pre.target\n'
			)

		for user in users:
			home = install_session.target / 'home' / user.username

			for comp in self.compositors:
				if comp == 'niri':
					self._provision_niri(home)
				else:
					self._provision_hyprland(home)

			install_session.arch_chroot(['chown', '-R', f'{user.username}:{user.username}', f'/home/{user.username}/.config'])

	def _provision_niri(self, home: Path) -> None:
		binds = (_ASSETS_DIR / 'niri/dms/binds.kdl').read_text().replace('{{TERMINAL_COMMAND}}', terminal_command())

		niri_dir = home / '.config/niri'
		dms_dir = niri_dir / 'dms'
		dms_dir.mkdir(parents=True, exist_ok=True)

		shutil.copy(_ASSETS_DIR / 'niri/niri.kdl', niri_dir / 'config.kdl')
		# input.kdl is a seed: dms regenerates it from its settings UI
		for name in ('colors.kdl', 'layout.kdl', 'alttab.kdl', 'outputs.kdl', 'cursor.kdl', 'input.kdl'):
			shutil.copy(_ASSETS_DIR / 'niri/dms' / name, dms_dir / name)
		(dms_dir / 'binds.kdl').write_text(binds)

	def _provision_hyprland(self, home: Path) -> None:
		# hyprland 0.55+ lua configs; dms.service starts via
		# hyprland-session.target on hyprland.start
		hypr_dir = home / '.config/hypr'
		dms_dir = hypr_dir / 'dms'
		dms_dir.mkdir(parents=True, exist_ok=True)

		for src, dest in (('hyprland.lua', hypr_dir), ('dms/binds.lua', dms_dir)):
			conf = (_ASSETS_DIR / 'hyprland' / src).read_text().replace('{{TERMINAL_COMMAND}}', terminal_command())
			(dest / Path(src).name).write_text(conf)

		for name in ('binds-user.lua', 'colors.lua', 'cursor.lua', 'layout.lua', 'outputs.lua', 'windowrules.lua'):
			shutil.copy(_ASSETS_DIR / 'hyprland/dms' / name, dms_dir / name)

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
