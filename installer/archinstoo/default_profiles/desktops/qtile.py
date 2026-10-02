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
		# ttf: bar renders as boxes without a scalable font
		# dbus-fast: optdep qtile warns about on every start
		# xwayland: the shipped "Qtile (Wayland)" session exits 1 without it
		return [
			'qtile',
			'ttf-liberation',
			'python-dbus-fast',
			'xorg-xwayland',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
