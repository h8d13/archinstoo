from enum import Enum, auto
from typing import TYPE_CHECKING, ClassVar, Self

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class DisplayServer(Enum):
	X11 = 'x11'
	Wayland = 'wayland'


class ProfileType(Enum):
	# top level default_profiles
	Server = 'server'
	Desktop = 'desktop'
	Xorg = 'xorg'
	Wayland = 'wayland'
	Minimal = 'minimal'
	Custom = 'custom'
	# detailed selection default_profiles
	ServerType = 'servertype'
	WindowMgr = 'window manager'
	DesktopEnv = 'desktop environment'
	CustomType = 'customtype'

	# Custom are place-holders
	# wayland is hidden in menu
	# it is not used 'standalone' usually as
	# deps of a DE/WM, just a base class
	# 'profile.py' and 'wayland.py' are
	# hidden by /lib/profile/profiles_handler.py


class GreeterType(Enum):
	Lightdm = 'lightdm-gtk-greeter'
	LightdmSlick = 'lightdm-slick-greeter'
	PlasmaLoginManager = 'plasma-login-manager'
	Sddm = 'sddm'
	Gdm = 'gdm'
	Ly = 'ly'
	Greetd = 'greetd'
	GreetdDms = 'dms-greeter'
	Regreet = 'regreet'
	CosmicSession = 'cosmic-greeter'

	@property
	def packages(self) -> list[str]:
		match self:
			case GreeterType.Lightdm:
				return ['lightdm', 'lightdm-gtk-greeter']
			case GreeterType.LightdmSlick:
				return ['lightdm', 'lightdm-slick-greeter']
			case GreeterType.PlasmaLoginManager:
				return ['plasma-login-manager']
			case GreeterType.Sddm:
				return ['sddm']
			case GreeterType.Gdm:
				return ['gdm']
			case GreeterType.Ly:
				return ['ly']
			case GreeterType.Greetd:
				return ['greetd']
			case GreeterType.GreetdDms:
				# the greeter itself ships with dms-shell-<compositor>
				return ['greetd']
			case GreeterType.Regreet:
				# regreet (GUI) runs inside the cage kiosk compositor
				return ['greetd', 'greetd-regreet', 'cage']
			case GreeterType.CosmicSession:
				return ['cosmic-greeter']

	@property
	def services(self) -> list[str]:
		match self:
			case GreeterType.Lightdm | GreeterType.LightdmSlick:
				return ['lightdm']
			case GreeterType.PlasmaLoginManager:
				return ['plasmalogin']
			case GreeterType.Ly:
				return ['ly@tty1']
			case GreeterType.Regreet | GreeterType.GreetdDms:
				return ['greetd']
			case _:
				return [self.value]

	@property
	def disabled_services(self) -> list[str]:
		# these take over vt1, so the getty that owns it has to go
		match self:
			case GreeterType.Ly | GreeterType.Regreet | GreeterType.GreetdDms:
				return ['getty@tty1']
			case _:
				return []


class SelectResult(Enum):
	NewSelection = auto()
	SameSelection = auto()
	ResetCurrent = auto()


class Profile:
	# ships a terminal keybind rather than a terminal: install_profile_config()
	# installs the one Terminal choice for these, so their package list stays fixed
	needs_terminal: bool = False

	# profiles that run on top of a compositor of the user's choosing; the
	# <name>_compositor custom_setting picks which of these sets to install
	compositor_packages: ClassVar[dict[str, list[str]]] = {}

	def __init__(
		self,
		name: str,
		profile_type: ProfileType,
		current_selection: list[Self] | None = None,
		packages: list[str] | None = None,
		services: list[str] | None = None,
	) -> None:
		self.name = name
		self.profile_type = profile_type
		self.custom_settings: dict[str, str | list[str] | None] = {}

		self.current_selection = list(current_selection or [])
		self._packages = list(packages or [])
		self._services = list(services or [])

	@property
	def packages(self) -> list[str]:
		return self._packages

	def effective_packages(self) -> list[str]:
		excluded = set(self.custom_settings.get('excluded_packages') or [])
		return [p for p in self.packages if p not in excluded]

	@property
	def services(self) -> list[str]:
		return self._services

	@property
	def default_greeter_type(self) -> GreeterType | None:
		return None

	# no-op hooks: subclasses override, args are the hook contract
	def install(self, install_session: Installer) -> None: ...  # pylint: disable=unused-argument

	def post_install(self, install_session: Installer) -> None: ...  # pylint: disable=unused-argument

	def provision(self, install_session: Installer, users: list[User]) -> None: ...  # pylint: disable=unused-argument

	def json(self) -> dict[str, str]:
		# Returns a json representation of the profile
		return {}

	def do_on_select(self) -> SelectResult | None:
		# Hook that will be called when a profile is selected
		# Usually for seat access
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
		# Returns the set of display servers required by this profile.
		# Aggregates requirements from sub-profiles if present.
		# Profiles inherit from XorgProfile or WaylandProfile to specify their display server.
		if self.current_selection:
			servers: set[DisplayServer] = set()
			for sub_profile in self.current_selection:
				servers.update(sub_profile.display_servers())
			return servers
		return set()

	def preview_text(self) -> str:
		# Override this method to provide a preview text for the profile
		return self.packages_text()

	def packages_text(self, include_sub_packages: bool = False) -> str:
		packages = set()

		if self.packages:
			packages = set(self.packages)

		if include_sub_packages:
			for sub_profile in self.current_selection:
				if sub_profile.packages:
					packages.update(sub_profile.packages)

		text = 'Installed packages' + ':\n'

		for pkg in sorted(packages):
			text += f'\t- {pkg}\n'

		return text
