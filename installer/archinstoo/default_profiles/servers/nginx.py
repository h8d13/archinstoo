from typing import override

from archinstoo.lib.profile.base import Profile, ProfileType


class NginxProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'nginx',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['nginx']

	@property
	@override
	def services(self) -> list[str]:
		return ['nginx']
