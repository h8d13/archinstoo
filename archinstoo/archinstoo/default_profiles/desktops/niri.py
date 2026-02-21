from typing import override

from archinstoo.default_profiles.profile import GreeterType, ProfileType
from archinstoo.default_profiles.wayland import WaylandProfile


class NiriProfile(WaylandProfile):
	def __init__(self) -> None:
		super().__init__(
			'Niri',
			ProfileType.WindowMgr,
		)

		self.custom_settings = {'seat_access': 'seatd'}

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
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
