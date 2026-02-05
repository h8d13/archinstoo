from typing import override

from archinstoo.default_profiles.profile import Profile, ProfileType


class TailscaleProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Tailscale',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['tailscale']

	@property
	@override
	def services(self) -> list[str]:
		return ['tailscaled']
