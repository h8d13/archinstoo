from typing import override

from archinstoo.lib.profile.base import Profile, ProfileType


class TomcatProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'tomcat',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['tomcat']

	@property
	@override
	def services(self) -> list[str]:
		return ['tomcat']
