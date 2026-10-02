from typing import override

from archinstoo.default_profiles.desktops import select_seat_access
from archinstoo.default_profiles.wayland import WaylandProfile
from archinstoo.lib.profile.base import GreeterType, ProfileType, seat_packages, seat_services


class HyprlandProfile(WaylandProfile):
	needs_terminal = True

	_default_greeter_non_seatd = GreeterType.Sddm

	def __init__(self) -> None:
		super().__init__('hyprland', ProfileType.WindowMgr)

		self.custom_settings = {'seat_access': None}

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'hyprland',
			'kitty',
			'dunst',
			'uwsm',
			'hyprlauncher',
			'xdg-desktop-portal-hyprland',
			'qt5-wayland',
			'qt6-wayland',
			'hyprpolkitagent',
			'grim',
			'slurp',
			'wl-clipboard',
			*seat_packages(self.custom_settings.get('seat_access')),
		]

	@property
	@override
	def services(self) -> list[str]:
		return seat_services(self.custom_settings.get('seat_access'))

	@override
	def do_on_select(self) -> None:
		self.custom_settings['seat_access'] = select_seat_access(
			'Hyprland',
			self.custom_settings.get('seat_access'),
		)
