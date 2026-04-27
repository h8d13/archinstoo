from archinstoo.lib.profile.base import Profile, ProfileType


class MinimalProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Minimal',
			ProfileType.Minimal,
		)
