from typing import override

from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class DeepinProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('Deepin', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'deepin',
			'deepin-terminal',
			'deepin-editor',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
