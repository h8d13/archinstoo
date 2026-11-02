from typing import override

from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class I3wmProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('i3-wm', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'i3-wm',
			'i3lock',
			'i3status',
			'i3blocks',
			'xss-lock',
			'lightdm-gtk-greeter',
			'lightdm',
			'dmenu',
			# i3-sensible-terminal searches a list, alacritty is in it
			'alacritty',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
