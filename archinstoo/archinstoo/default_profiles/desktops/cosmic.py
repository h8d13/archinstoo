from typing import override

from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class CosmicProfile(WaylandProfile):
	def __init__(self) -> None:
		super().__init__('Cosmic', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'cosmic',
			'xdg-user-dirs',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.CosmicSession
