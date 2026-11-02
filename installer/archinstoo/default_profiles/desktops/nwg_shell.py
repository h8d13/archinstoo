from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.desktops import select_seat_access
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


class NwgShellProfile(WaylandProfile):
	# sway only: the installer's -hypr preset is hyprland.conf, which
	# Hyprland >= 0.55 ignores for hyprland.lua
	_default_greeter_non_seatd = GreeterType.NwgHello

	def __init__(self) -> None:
		super().__init__('nwg-shell', ProfileType.Shell)

		self.custom_settings = {'seat_access': None}

	@property
	@override
	def packages(self) -> list[str]:
		# nwg-shell is the metapackage: sway, foot, panel, dock, drawer,
		# nwg-hello and the rest come as its depends
		return [
			'nwg-shell',
			# sway-portals.conf: gtk default, wlr for screencast;
			# nwg-shell pulls neither
			'xdg-desktop-portal-gtk',
			'xdg-desktop-portal-wlr',
			*seat_packages(self.custom_settings.get('seat_access')),
		]

	@property
	@override
	def services(self) -> list[str]:
		return seat_services(self.custom_settings.get('seat_access'))

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		super().provision(install_session, users)

		# the package ships no configs: the installer copies its skel into
		# the user's $HOME. -w skips the prompts, -s the `systemctl reboot`
		# that -w otherwise ends on
		for user in users:
			info(f'Running nwg-shell-installer for {user.username}')
			install_session.arch_chroot(
				['nwg-shell-installer', '-w', '-s'],
				run_as=user.username,
			)

	@override
	def do_on_select(self) -> None:
		self.custom_settings['seat_access'] = select_seat_access(
			'nwg-shell',
			self.custom_settings.get('seat_access'),
		)
