from typing import override

from archinstoo.lib.profile.base import DisplayServer, Profile, ProfileType


class XorgProfile(Profile):
	def __init__(
		self,
		name: str = 'xorg',
		profile_type: ProfileType = ProfileType.Xorg,
	):
		super().__init__(
			name,
			profile_type,
		)

	@override
	def preview_text(self) -> str:
		text = f'Type: {self.profile_type.value} (Xorg)'
		if packages := self.packages_text():
			text += f'\n{packages}'

		return text

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'xorg-server',
		]

	@override
	def display_servers(self) -> set[DisplayServer]:
		return {DisplayServer.X11}
