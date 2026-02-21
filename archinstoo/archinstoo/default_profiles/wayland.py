from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.profile import DisplayServer, Profile, ProfileType
from archinstoo.lib.translationhandler import tr

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class WaylandProfile(Profile):
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
				install_session.arch_chroot(f'usermod -a -G seat {user.username}')

	@override
	def preview_text(self) -> str:
		text = tr('Type: {} (Wayland)').format(self.profile_type.value)
		if packages := self.packages_text():
			text += f'\n{packages}'

		return text

	@override
	def display_servers(self) -> set[DisplayServer]:
		return {DisplayServer.Wayland}
