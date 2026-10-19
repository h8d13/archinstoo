from typing import override

from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class MateProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('mate', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'mate',
			'mate-extra',
			# Secret portal backend (org.freedesktop.secrets), mate-
			# portals.conf names it, groups only optdep it
			'gnome-keyring',
			# mate-portals.conf names gtk, nothing in the
			# mate groups pulls it
			'xdg-desktop-portal-gtk',
			# wallpaper/screenshot/background: mate-portals.conf never names
			# it, picked via xapp.portal UseIn
			'xdg-desktop-portal-xapp',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
