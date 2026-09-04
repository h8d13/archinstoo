from typing import override

from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class QtileProfile(XorgProfile):
	needs_terminal = True

	def __init__(self) -> None:
		super().__init__('qtile', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'qtile',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
