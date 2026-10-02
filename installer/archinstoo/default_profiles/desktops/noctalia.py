import shutil
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from archinstoo.default_profiles.desktops import select_compositor, select_seat_access
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.output import debug
from archinstoo.lib.profile.base import GreeterType, ProfileType, seat_packages, seat_services

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User

# assets follow the canonical per-compositor integration docs (docs.noctalia.dev
# renders these): https://github.com/noctalia-dev/noctalia/tree/main/docs/user/compositor-settings
_ASSETS_DIR = Path(__file__).parent / 'noctalia_assets'


# compositor -> config dir under ~/.config; every file in the matching
# noctalia_assets/<compositor>/ dir is provisioned into it
_COMPOSITOR_CONFIG_DIRS = {
	'niri': 'niri',
	'hyprland': 'hypr',
	'sway': 'sway',
	'labwc': 'labwc',
}


class NoctaliaProfile(WaylandProfile):
	needs_terminal = True

	# noctalia v5: native wayland shell (bar, launcher, lock, notifications,
	# clipboard, polkit agent), no qt/gtk deps; compositor is a free choice
	compositor_packages: ClassVar[dict[str, list[str]]] = {
		'niri': ['niri', 'xdg-desktop-portal-gnome', 'xorg-xwayland'],
		# uwsm backs the "Hyprland (uwsm)" session entry the hyprland package ships
		'hyprland': ['hyprland', 'xdg-desktop-portal-hyprland', 'uwsm'],
		'sway': ['sway', 'xdg-desktop-portal-wlr', 'xorg-xwayland'],
		'labwc': ['labwc', 'xdg-desktop-portal-wlr', 'xorg-xwayland'],
	}

	# noctalia-greeter (greetd) is not packaged in the arch repos yet;
	# fall back to sddm like the plain hyprland profile
	_default_greeter_non_seatd = GreeterType.Sddm

	def __init__(self) -> None:
		super().__init__('noctalia', ProfileType.WindowMgr)

		self.custom_settings = {'noctalia_compositor': 'niri', 'seat_access': None}

	@property
	@override
	def packages(self) -> list[str]:
		return [
			*self.compositor_packages[self.compositor],
			'noctalia',
			# noctalia resolves fonts via fontconfig (sans-serif default);
			# bare installs ship none, so seed one sans + one mono
			'inter-font',
			'ttf-jetbrains-mono-nerd',
			*seat_packages(self.custom_settings.get('seat_access')),
		]

	@property
	@override
	def services(self) -> list[str]:
		return seat_services(self.custom_settings.get('seat_access'))

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		super().provision(install_session, users)

		# noctalia starts via the compositor's autostart hook; only the
		# compositor config is provisioned, the shell configures itself
		for user in users:
			config_dir = install_session.target / 'home' / user.username / '.config'
			dest_dir = config_dir / _COMPOSITOR_CONFIG_DIRS[self.compositor]
			dest_dir.mkdir(parents=True, exist_ok=True)

			for asset in sorted((_ASSETS_DIR / self.compositor).iterdir()):
				dest = dest_dir / asset.name
				debug(f'Writing {dest} for {user.username}')
				shutil.copy(asset, dest)

			install_session.chown_tree(user.username, f'/home/{user.username}/.config')

	@override
	def do_on_select(self) -> None:
		self.custom_settings['noctalia_compositor'] = select_compositor(
			'Noctalia',
			list(self.compositor_packages),
			self.compositor,
		)
		self.custom_settings['seat_access'] = select_seat_access(
			'Noctalia',
			self.custom_settings.get('seat_access'),
		)
