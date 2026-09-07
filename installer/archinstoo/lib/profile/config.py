from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self, TypedDict

from archinstoo.lib.hardware import GfxDriver, GfxPackage
from archinstoo.lib.profile.base import DisplayServer, GreeterType, Profile

if TYPE_CHECKING:
	from archinstoo.lib.profile.profiles_handler import ProfileSerialization


class _ProfileConfigurationSerialization(TypedDict):
	profiles: list[ProfileSerialization]
	gfx_driver: str | None
	gfx_packages: list[str]
	greeter: str | None


@dataclass
class ProfileConfiguration:
	profiles: list[Profile] = field(default_factory=list)
	gfx_driver: GfxDriver | None = None
	# only read when gfx_driver is Custom
	gfx_packages: list[GfxPackage] = field(default_factory=list)
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
			'gfx_driver': self.gfx_driver.value if self.gfx_driver else None,
			'gfx_packages': [p.value for p in self.gfx_packages],
			'greeter': self.greeter.value if self.greeter else None,
		}

	@classmethod
	def parse_arg(cls, arg: _ProfileConfigurationSerialization) -> Self:
		from archinstoo.lib.profile.profiles_handler import ProfileHandler

		handler = ProfileHandler()
		profiles = [profile for profile_data in arg.get('profiles', []) if (profile := handler.parse_profile_config(profile_data))]

		greeter = arg.get('greeter', None)
		gfx_driver = arg.get('gfx_driver', None)
		# unknown names are dropped, the same way kernels are parsed
		gfx_packages = [GfxPackage(p) for p in arg.get('gfx_packages') or [] if p in GfxPackage._value2member_map_]

		return cls(
			profiles,
			GfxDriver(gfx_driver) if gfx_driver else None,
			gfx_packages,
			GreeterType(greeter) if greeter else None,
		)
