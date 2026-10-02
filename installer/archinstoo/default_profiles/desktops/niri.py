from typing import override

from archinstoo.default_profiles.desktops import select_seat_access
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import ProfileType, seat_packages, seat_services


class NiriProfile(WaylandProfile):
	needs_terminal = True

	def __init__(self) -> None:
		super().__init__(
			'niri',
			ProfileType.WindowMgr,
		)

		self.custom_settings = {'seat_access': None}

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'niri',
			'alacritty',
			'fuzzel',
			'mako',
			'xwayland-satellite',
			'waybar',
			'swaybg',
			'swayidle',
			'swaylock',
			'xdg-desktop-portal-gnome',
			'xdg-desktop-portal-gtk',
			*seat_packages(self.custom_settings.get('seat_access')),
		]

	@property
	@override
	def services(self) -> list[str]:
		return seat_services(self.custom_settings.get('seat_access'))

	@override
	def do_on_select(self) -> None:
		self.custom_settings['seat_access'] = select_seat_access(
			'Niri',
			self.custom_settings.get('seat_access'),
		)
