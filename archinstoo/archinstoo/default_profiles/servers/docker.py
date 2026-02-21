from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.profile import Profile, ProfileType

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class DockerProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'Docker',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['docker']

	@property
	@override
	def services(self) -> list[str]:
		return ['docker']

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		for user in users:
			install_session.arch_chroot(f'usermod -a -G docker {user.username}')
