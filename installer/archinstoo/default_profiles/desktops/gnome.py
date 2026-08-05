from typing import override

from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class GnomeProfile(WaylandProfile):
	def __init__(self) -> None:
		super().__init__('gnome', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		# explicit list instead of the 'gnome' group: the group pulls ~60
		# packages (games, maps, weather, music, tour...) that a user can
		# still install after the fact
		return [
			'gnome-shell',
			'gnome-session',
			'gnome-terminal',
			'gnome-control-center',
			'gnome-settings-daemon',
			'nautilus',
			'xdg-desktop-portal-gnome',
			'gnome-tweaks',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Gdm
