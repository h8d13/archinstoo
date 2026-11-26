from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from archinstoo.lib.models.profile import DisplayServer, GreeterType
	from archinstoo.lib.profile.base import Profile


@dataclass
class ProfileConfiguration:
	profiles: list[Profile] = field(default_factory=list)
	greeter: GreeterType | None = None

	def has_desktop_profile(self) -> bool:
		return any(p.is_desktop_profile() for p in self.profiles)

	def display_servers(self) -> set[DisplayServer]:
		servers: set[DisplayServer] = set()
		for profile in self.profiles:
			servers.update(profile.display_servers())
		return servers

	def is_greeter_supported(self) -> bool:
		return any(p.is_greeter_supported() for p in self.profiles)
