from typing import override

from archinstall.default_profiles.profile import Profile, ProfileType


class JavaProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Java',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['jre-openjdk-headless']
