from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.profile import DisplayServer, GreeterType, Profile, ProfileType
from archinstoo.lib.translationhandler import tr

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class WaylandProfile(Profile):
	# seatd is incompatible with logind-based greeters (lightdm/sddm/gdm);
	# subclasses set their preferred non-seatd greeter here.
	_default_greeter_non_seatd: GreeterType = GreeterType.Lightdm

	def __init__(
		self,
		name: str = 'Wayland',
		profile_type: ProfileType = ProfileType.Wayland,
		advanced: bool = False,
	):
		super().__init__(
			name,
			profile_type,
			advanced=advanced,
		)

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		if self.custom_settings.get('seat_access') == 'seatd':
			for user in users:
				install_session.arch_chroot(['usermod', '-a', '-G', 'seat', user.username])

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		if self.custom_settings.get('seat_access') == 'seatd':
			return GreeterType.Ly
		return self._default_greeter_non_seatd

	@override
	def preview_text(self) -> str:
		text = tr('Type: {} (Wayland)').format(self.profile_type.value)
		if packages := self.packages_text():
			text += f'\n{packages}'

		return text

	@override
	def display_servers(self) -> set[DisplayServer]:
		return {DisplayServer.Wayland}
