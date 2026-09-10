from typing import override

from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class PlasmaProfile(WaylandProfile):
	def __init__(self) -> None:
		super().__init__('kde-plasma', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'plasma-desktop',
			'plasma-pa',
			'kscreen',
			'konsole',
			'kate',
			'dolphin',
			'ark',
			'bluedevil',
			'plasma-thunderbolt',
			# portal backend: flatpak, screen share, wayland-era file pickers https://github.com/archlinux/archinstall/issues/1629
			'xdg-desktop-portal-kde',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.PlasmaLoginManager
