from typing import override

from archinstoo.lib.profile.base import Profile, ProfileType


class CockpitProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'cockpit',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['cockpit', 'cockpit-storaged', 'cockpit-packagekit']

	@property
	@override
	def services(self) -> list[str]:
		return ['cockpit.socket']
