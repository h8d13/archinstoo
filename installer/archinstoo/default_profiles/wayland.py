from typing import TYPE_CHECKING, override

from archinstoo.lib.profile.base import DisplayServer, GreeterType, Profile, ProfileType

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class WaylandProfile(Profile):
	# seatd is incompatible with logind-based greeters (lightdm/sddm/gdm);
	# subclasses set their preferred non-seatd greeter here.
	_default_greeter_non_seatd: GreeterType = GreeterType.Lightdm

	def __init__(
		self,
		name: str = 'wayland',
		profile_type: ProfileType = ProfileType.Wayland,
	):
		super().__init__(
			name,
			profile_type,
		)

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		if self.custom_settings.get('seat_access') == 'seatd':
			for user in users:
				install_session.arch_chroot(['usermod', '-a', '-G', 'seat', user.username])

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		# Graphical display managers hold a session with DRM master open at handoff,
		# so a seatd-based compositor (sway/niri/etc.) can't take over the GPU.
		# TTY/session-transparent greeters (ly, greetd, cosmic-greeter) don't.
		if self.custom_settings.get('seat_access') == 'seatd':
			return GreeterType.Ly
		return self._default_greeter_non_seatd

	@override
	def preview_text(self) -> str:
		text = f'Type: {self.profile_type.value} (Wayland)'
		if packages := self.packages_text():
			text += f'\n{packages}'

		return text

	@override
	def display_servers(self) -> set[DisplayServer]:
		return {DisplayServer.Wayland}
