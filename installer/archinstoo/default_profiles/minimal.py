from archinstoo.lib.models.profile import ProfileType
from archinstoo.lib.profile.base import Profile


class MinimalProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'minimal',
			ProfileType.Minimal,
		)
