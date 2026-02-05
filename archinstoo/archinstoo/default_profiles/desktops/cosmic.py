from typing import override

from archinstoo.default_profiles.profile import GreeterType, ProfileType
from archinstoo.default_profiles.wayland import WaylandProfile


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
