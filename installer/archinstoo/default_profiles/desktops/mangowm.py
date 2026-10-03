from typing import override

from archinstoo.default_profiles.desktops import select_seat_access
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import ProfileType, seat_packages, seat_services


class MangowmProfile(WaylandProfile):
	needs_terminal = True

	def __init__(self) -> None:
		super().__init__(
			'mangowm',
			ProfileType.WindowMgr,
		)

		self.custom_settings = {'seat_access': None}

	@property
	@override
	def packages(self) -> list[str]:
		# /etc/mango/config.conf is read when ~/.config/mango has none; its
		# only spawns are these two
		return [
			'mangowm',
			'foot',
			'rofi',
			*seat_packages(self.custom_settings.get('seat_access')),
			'xdg-desktop-portal-gtk',  # mango-portals.conf: gtk default, wlr for screencast; mangowm pulls neither
			'xdg-desktop-portal-wlr',
		]

	@property
	@override
	def services(self) -> list[str]:
		return seat_services(self.custom_settings.get('seat_access'))

	@override
	def do_on_select(self) -> None:
		self.custom_settings['seat_access'] = select_seat_access(
			'mangowm',
			self.custom_settings.get('seat_access'),
		)
