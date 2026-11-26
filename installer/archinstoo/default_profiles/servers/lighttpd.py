from typing import override

from archinstoo.lib.models.profile import ProfileType
from archinstoo.lib.profile.base import Profile


class LighttpdProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'lighttpd',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['lighttpd']

	@property
	@override
	def services(self) -> list[str]:
		return ['lighttpd']
