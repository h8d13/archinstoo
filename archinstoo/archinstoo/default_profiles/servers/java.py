from typing import override

from archinstoo.lib.profile.base import Profile, ProfileType


class JavaProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'java',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['jre-openjdk-headless']
