from enum import Enum, auto
from typing import TYPE_CHECKING, Self

from archinstoo.lib.translationhandler import tr

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class ProfileType(Enum):
	# top level default_profiles
	Server = 'Server'
	Desktop = 'Desktop'
	Xorg = 'Xorg'
	Wayland = 'Wayland'
	Minimal = 'Minimal'
	Custom = 'Custom'
	# detailed selection default_profiles
	ServerType = 'ServerType'
	WindowMgr = 'Window Manager'
	DesktopEnv = 'Desktop Environment'
	CustomType = 'CustomType'

	# Custom are place-holders
	# wayland is hidden in menu
	# it is not used 'standalone' usually as
	# deps of a DE/WM, just a base class
	# 'profile.py' and 'wayland.py' are
	# hidden by /lib/profile/profiles_handler.py


# XorgProfile: just provides xorg-server package standalone
# + display_servers() -> X11
# WaylandProfile returns nothing, expected to be deps
# this reduces by about 140 pkgs ISSUES#4057
# which was added in hardware.py regardless


class DisplayServer(Enum):
	X11 = 'x11'
	Wayland = 'wayland'


class GreeterType(Enum):
	Nogreeter = ''
	Lightdm = 'lightdm-gtk-greeter'
	LightdmSlick = 'lightdm-slick-greeter'
	PlasmaLoginManager = 'plasma-login-manager'
	Sddm = 'sddm'
	Gdm = 'gdm'
	Ly = 'ly'
	Greetd = 'greetd'
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
		current_selection: list[Self] = [],
		packages: list[str] = [],
		services: list[str] = [],
		advanced: bool = False,
	) -> None:
		self.name = name
		self.profile_type = profile_type
		self.custom_settings: dict[str, str | None] = {}
		self.advanced = advanced

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

	def install(self, install_session: Installer) -> None: ...

	def post_install(self, install_session: Installer) -> None: ...

	def provision(self, install_session: Installer, users: list[User]) -> None: ...

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
		top_levels = [ProfileType.Desktop, ProfileType.Server, ProfileType.Xorg, ProfileType.Custom]
		return self.profile_type in top_levels

	def is_desktop_profile(self) -> bool:
		return self.profile_type == ProfileType.Desktop

	def is_server_type_profile(self) -> bool:
		return self.profile_type == ProfileType.ServerType

	def is_desktop_type_profile(self) -> bool:
		return self.profile_type == ProfileType.DesktopEnv or self.profile_type == ProfileType.WindowMgr

	def is_greeter_supported(self) -> bool:
		return self.profile_type == ProfileType.Desktop

	def display_servers(self) -> set[DisplayServer]:
		from archinstoo.lib.profile.profiles_handler import ProfileHandler

		handler = ProfileHandler()
		return handler.display_servers(self)

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
