from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self, TypedDict

from archinstoo.lib.output import warn
from archinstoo.lib.profile.base import DisplayServer, GreeterType, Profile

if TYPE_CHECKING:
	from archinstoo.lib.profile.profiles_handler import ProfileSerialization


class _ProfileConfigurationSerialization(TypedDict):
	profiles: list[ProfileSerialization]
	greeter: str | None


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

	def json(self) -> _ProfileConfigurationSerialization:
		from archinstoo.lib.profile.profiles_handler import ProfileHandler

		handler = ProfileHandler()
		return {
			'profiles': [handler.to_json(p) for p in self.profiles],
			'greeter': self.greeter.value if self.greeter else None,
		}

	@classmethod
	def parse_arg(cls, arg: _ProfileConfigurationSerialization) -> Self:
		from archinstoo.lib.profile.profiles_handler import ProfileHandler

		handler = ProfileHandler()
		profiles = [profile for profile_data in arg.get('profiles', []) if (profile := handler.parse_profile_config(profile_data))]

		greeter = arg.get('greeter', None)

		config = cls(
			profiles,
			GreeterType(greeter) if greeter else None,
		)

		# the menu gates this on the selection; a hand-written config does not,
		# and install_profile_config would drop it without a word after pacstrap
		# had already run
		if config.greeter and not config.is_greeter_supported():
			warn(f'Greeter {config.greeter.value} in the config: no selected profile supports one, it will be skipped')

		return config
