from typing import override

from archinstoo.default_profiles.desktops import terminal_command
from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class QtileProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('qtile', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'qtile',
			terminal_command(),
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
