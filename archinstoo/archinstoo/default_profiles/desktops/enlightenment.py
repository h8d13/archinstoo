from typing import override

from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class EnlightenmentProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Enlightenment', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'enlightenment',
			'terminology',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
