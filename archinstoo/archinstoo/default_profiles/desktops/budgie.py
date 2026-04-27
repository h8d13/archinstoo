from typing import override

from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType


class BudgieProfile(WaylandProfile):
	def __init__(self) -> None:
		super().__init__('Budgie', ProfileType.DesktopEnv)

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'materia-gtk-theme',
			'budgie',
			'konsole',
			'dolphin',
			'papirus-icon-theme',
		]

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Sddm
