from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from archinstall.lib.translationhandler import tr

if TYPE_CHECKING:
	from ..lib.installer import Installer


class ProfileType(Enum):
	# top level default_profiles
	Server = 'Server'
	Desktop = 'Desktop'
	Xorg = 'Xorg'
	Minimal = 'Minimal'
	Custom = 'Custom'
	# detailed selection default_profiles
	ServerType = 'ServerType'
	WindowMgr = 'Window Manager'
	DesktopEnv = 'Desktop Environment'
	CustomType = 'CustomType'
	# special things
	Tailored = 'Tailored'
	Application = 'Application'


class DisplayServer(Enum):
	X11 = 'x11'
	Wayland = 'wayland'


class GreeterType(Enum):
	NoGreeter = ''
	Lightdm = 'lightdm-gtk-greeter'
	LightdmSlick = 'lightdm-slick-greeter'
	Sddm = 'sddm'
	Gdm = 'gdm'
	Ly = 'ly'
	CosmicSession = 'cosmic-greeter'


class SelectResult(Enum):
	NewSelection = auto()
	SameSelection = auto()
	ResetCurrent = auto()


class Profile:
	def __init__(
		self,
		name: str,
		profile_type: ProfileType,
		current_selection: list['Profile'] = [],
		packages: list[str] = [],
		services: list[str] = [],
		support_greeter: bool = False,
		advanced: bool = False,
	) -> None:
		self.name = name
		self.profile_type = profile_type
		self.custom_settings: dict[str, str | None] = {}
		self.advanced = advanced

		self._support_greeter = support_greeter

		# self.gfx_driver: str | None = None

		self.current_selection = current_selection
		self._packages = packages
		self._services = services

	@property
	def packages(self) -> list[str]:
		return self._packages

	@property
	def services(self) -> list[str]:
		return self._services

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return None

	def _advanced_check(self) -> bool:
		"""
		Used to control if the Profile() should be visible or not in different contexts.
		Returns True if --advanced is given on a Profile(advanced=True) instance.
		"""
		from archinstall.lib.args import arch_config_handler

		return self.advanced is False or arch_config_handler.args.advanced is True

	def install(self, install_session: 'Installer') -> None: ...

	def post_install(self, install_session: 'Installer') -> None: ...

	def json(self) -> dict[str, str]:
		"""
		Returns a json representation of the profile
		"""
		return {}

	def do_on_select(self) -> SelectResult | None:
		"""
		Hook that will be called when a profile is selected
		Usually for seat access
		"""
		return SelectResult.NewSelection

	def current_selection_names(self) -> list[str]:
		if self.current_selection:
			return [s.name for s in self.current_selection]
		return []

	def reset(self) -> None:
		self.current_selection = []

	def is_top_level_profile(self) -> bool:
		top_levels = [ProfileType.Desktop, ProfileType.Server, ProfileType.Xorg, ProfileType.Minimal, ProfileType.Custom]
		return self.profile_type in top_levels

	def is_desktop_profile(self) -> bool:
		return self.profile_type == ProfileType.Desktop if self._advanced_check() else False

	def is_server_type_profile(self) -> bool:
		return self.profile_type == ProfileType.ServerType

	def is_desktop_type_profile(self) -> bool:
		return (self.profile_type == ProfileType.DesktopEnv or self.profile_type == ProfileType.WindowMgr) if self._advanced_check() else False

	def is_xorg_type_profile(self) -> bool:
		return self.profile_type == ProfileType.Xorg if self._advanced_check() else False

	def is_tailored(self) -> bool:
		return self.profile_type == ProfileType.Tailored

	def is_custom_type_profile(self) -> bool:
		return self.profile_type == ProfileType.CustomType

	def is_greeter_supported(self) -> bool:
		return self._support_greeter

	def display_servers(self) -> set[DisplayServer]:
		from ..lib.profile.profiles_handler import profile_handler

		return profile_handler.display_servers(self)

	def preview_text(self) -> str:
		"""
		Override this method to provide a preview text for the profile
		"""
		return self.packages_text()

	def packages_text(self, include_sub_packages: bool = False) -> str:
		packages = set()

		if self.packages:
			packages = set(self.packages)

		if include_sub_packages:
			for sub_profile in self.current_selection:
				if sub_profile.packages:
					packages.update(sub_profile.packages)

		text = tr('Installed packages') + ':\n'

		for pkg in sorted(packages):
			text += f'\t- {pkg}\n'

		return text
