from typing import TYPE_CHECKING, ClassVar, override

from archinstoo.default_profiles.desktops import select_compositor, select_seat_access
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.output import info
from archinstoo.lib.profile.base import (
	GreeterType,
	ProfileType,
	seat_packages,
	seat_services,
)

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class DmsProfile(WaylandProfile):
	# the Terminal choice still lands in $TERMINAL, but the keybind
	# `dms setup` writes is pinned to alacritty, so that one ships here
	needs_terminal = True

	# dux-shell (dms-shell before 2.0.0) is compositor-agnostic, so these
	# only carry the compositor
	compositor_packages: ClassVar[dict[str, list[str]]] = {
		'niri': [
			'niri',
			'xdg-desktop-portal-gnome',
			'gnome-keyring',
			'xorg-xwayland',
		],
		# uwsm backs the "Hyprland (uwsm)" session entry the
		# hyprland package ships
		'hyprland': [
			'hyprland',
			'xdg-desktop-portal-hyprland',
			'xdg-desktop-portal-gtk',
			'uwsm',
		],
		# mango-portals.conf: gtk default, wlr for screencast;
		# mangowm pulls neither
		'mango': [
			'mangowm',
			'xdg-desktop-portal-gtk',
			'xdg-desktop-portal-wlr',
		],
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

		self.custom_settings = {'dms_compositor': 'niri', 'seat_access': None}

	@property
	@override
	def packages(self) -> list[str]:
		return [
			*self.compositor_packages[self.compositor],
			'dux-shell',
			'matugen',
			'cava',
			'kimageformats',
			'alacritty',
			# dms defaults: Inter Variable + Fira Code. the shell bundles
			# both privately, but doctor <= 1.5.3 only checks fontconfig,
			# and the terminal needs a real mono font anyway
			'inter-font',
			'ttf-fira-code',
			*seat_packages(self.custom_settings.get('seat_access')),
		]

	@property
	@override
	def services(self) -> list[str]:
		return seat_services(self.custom_settings.get('seat_access'))

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		super().provision(install_session, users)

		# `dms setup headless` writes the compositor config and the dms/
		# overrides, then `systemctl --user add-wants` dms.service on the
		# compositor's own unit (niri.service, hyprland-session.target,
		# mango-session.target). if that fails the config starts the shell
		# itself, so no global enable here: graphical-session.target would
		# double it there and start it under any other DE too.
		# it has to run as the user: everything lands under their $HOME
		for user in users:
			info(
				f'Running dms setup for {user.username} '
				f'({self.compositor})'
			)
			install_session.arch_chroot(
				[
					'dms',
					'setup',
					'headless',
					'--compositor',
					self.compositor,
					'--terminal',
					'alacritty',
					'--skip-existing',
				],
				run_as=user.username,
			)

	@override
	def do_on_select(self) -> None:
		self.custom_settings['dms_compositor'] = select_compositor(
			'Dux Shell',
			list(self.compositor_packages),
			self.compositor,
		)
		self.custom_settings['seat_access'] = select_seat_access(
			'DMS',
			self.custom_settings.get('seat_access'),
		)
