from typing import override

from archinstoo.default_profiles.profile import Profile, ProfileType


class HttpdProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Httpd',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['apache']

	@property
	@override
	def services(self) -> list[str]:
		return ['httpd']
