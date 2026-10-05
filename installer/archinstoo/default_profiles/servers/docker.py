from typing import TYPE_CHECKING, override

from archinstoo.lib.authentication.accounts import add_to_group
from archinstoo.lib.profile.base import Profile, ProfileType

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


class DockerProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'docker',
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
		add_to_group(install_session, 'docker', [user.username for user in users])
