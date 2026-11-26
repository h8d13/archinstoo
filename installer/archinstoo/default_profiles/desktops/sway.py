from typing import override

from archinstoo.default_profiles.desktops import select_seat_access
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.models.profile import ProfileType, seat_packages


class SwayProfile(WaylandProfile):
	def __init__(self) -> None:
		super().__init__(
			'sway',
			ProfileType.WindowMgr,
		)

		self.custom_settings = {'seat_access': None}

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'sway',
			'foot',
			'swaybg',
			'swaylock',
			'swayidle',
			'wmenu',
			'brightnessctl',
			'grim',
			'slurp',
			'pavucontrol',
			'xorg-xwayland',
			*seat_packages(self.seat_access),
			# sway-portals.conf: gtk default, wlr for
			# screencast; sway pulls neither
			'xdg-desktop-portal-gtk',
			'xdg-desktop-portal-wlr',
		]

	@override
	def do_on_select(self) -> None:
		self.custom_settings['seat_access'] = select_seat_access(
			'Sway', self.seat_access
		)
