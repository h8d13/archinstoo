from typing import TYPE_CHECKING, ClassVar, Self

from archinstoo.lib.models.profile import (
	DisplayServer,
	GreeterType,
	ProfileType,
	SelectResult,
)
from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class Profile:
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
	def compositor(self) -> str:
		# set by the menu, one of compositor_packages
		return str(self.custom_settings[f'{self.name}_compositor'])

	@property
	def packages(self) -> list[str]:
		return self._packages

	def effective_packages(self) -> list[str]:
		excluded = set(self.custom_settings.get('excluded_packages') or [])
		if excluded:
			matched = excluded & set(self.packages)
			debug(
				f'{self.name}: excluding {sorted(matched)}; '
				f'unmatched: {sorted(excluded - matched)}'
			)
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
		top_levels = [
			ProfileType.Desktop,
			ProfileType.Server,
			ProfileType.Xorg,
			ProfileType.Custom,
		]
		return self.profile_type in top_levels

	def is_desktop_profile(self) -> bool:
		return self.profile_type == ProfileType.Desktop

	def is_server_type_profile(self) -> bool:
		return self.profile_type == ProfileType.ServerType

	def is_desktop_type_profile(self) -> bool:
		return self.profile_type in {
			ProfileType.DesktopEnv,
			ProfileType.WindowMgr,
			ProfileType.Shell,
		}

	def is_shell_profile(self) -> bool:
		return self.profile_type == ProfileType.Shell

	def is_greeter_supported(self) -> bool:
		return self.profile_type == ProfileType.Desktop

	def display_servers(self) -> set[DisplayServer]:
		# Returns the set of display servers required by this profile.
		# Aggregates requirements from sub-profiles if present.
		# Profiles inherit from XorgProfile or WaylandProfile to specify
		# their display server.
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

		text = 'Installed packages:\n'

		for pkg in sorted(packages):
			text += f'\t- {pkg}\n'

		return text
