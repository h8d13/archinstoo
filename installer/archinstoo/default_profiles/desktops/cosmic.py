from typing import override

from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class CosmicProfile(WaylandProfile):
	def __init__(self) -> None:
		super().__init__('cosmic', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		# the group's gnome-keyring-pam brings the Secret portal backend
		return ['@cosmic-desktop']

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.CosmicSession
