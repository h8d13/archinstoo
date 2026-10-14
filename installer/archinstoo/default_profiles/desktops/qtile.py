from typing import override

from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.profile.base import DisplayServer, GreeterType, ProfileType


class QtileProfile(XorgProfile):
	needs_terminal = True

	def __init__(self) -> None:
		super().__init__('qtile', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		# ttf: bar renders as boxes without a scalable font
		return [
			'qtile',
			'liberation-fonts-all',
		]

	@override
	def display_servers(self) -> set[DisplayServer]:
		# the package ships a "Qtile (Wayland)" session next to the X11 one,
		# which exits 1 without the Xwayland the wayland server brings
		return {DisplayServer.X11, DisplayServer.Wayland}

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
