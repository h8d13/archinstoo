from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self, TypedDict

from archinstall.default_profiles.profile import DisplayServer, GreeterType, Profile
from archinstall.lib.hardware import GfxDriver

if TYPE_CHECKING:
	from archinstall.lib.profile.profiles_handler import ProfileSerialization


class _ProfileConfigurationSerialization(TypedDict):
	profiles: list[ProfileSerialization]
	gfx_driver: str | None
	greeter: str | None


@dataclass
class ProfileConfiguration:
	profiles: list[Profile] = field(default_factory=list)
	gfx_driver: GfxDriver | None = None
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
		from archinstall.lib.profile.profiles_handler import ProfileHandler

		handler = ProfileHandler()
		return {
			'profiles': [handler.to_json(p) for p in self.profiles],
			'gfx_driver': self.gfx_driver.value if self.gfx_driver else None,
			'greeter': self.greeter.value if self.greeter else None,
		}

	@classmethod
	def parse_arg(cls, arg: _ProfileConfigurationSerialization) -> Self:
		from archinstall.lib.profile.profiles_handler import ProfileHandler

		handler = ProfileHandler()
		profiles = [profile for profile_data in arg.get('profiles', []) if (profile := handler.parse_profile_config(profile_data))]

		greeter = arg.get('greeter', None)
		gfx_driver = arg.get('gfx_driver', None)

		return cls(
			profiles,
			GfxDriver(gfx_driver) if gfx_driver else None,
			GreeterType(greeter) if greeter else None,
		)
