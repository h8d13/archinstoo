from typing import override

from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class XmonadProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('xmonad', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'xmonad',
			'ghc-xmonad-contrib',
			'xterm',
			'dmenu',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
