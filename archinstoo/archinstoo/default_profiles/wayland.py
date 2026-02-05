from typing import override

from archinstoo.default_profiles.profile import DisplayServer, Profile, ProfileType


class WaylandProfile(Profile):
	def __init__(
		self,
		name: str = 'Wayland',
		profile_type: ProfileType = ProfileType.Wayland,
		advanced: bool = False,
	):
		super().__init__(
			name,
			profile_type,
			advanced=advanced,
		)

	@override
	def display_servers(self) -> set[DisplayServer]:
		return {DisplayServer.Wayland}
