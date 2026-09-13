from typing import override

from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class CinnamonProfile(XorgProfile):
	def __init__(self) -> None:
		super().__init__('cinnamon', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'cinnamon',
			'system-config-printer',
			'gnome-keyring',  # Secret portal backend (org.freedesktop.secrets), x-cinnamon-portals.conf names it, groups only optdep it
			'gnome-terminal',
			'engrampa',
			'gnome-screenshot',
			'gvfs-smb',
			'xed',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
