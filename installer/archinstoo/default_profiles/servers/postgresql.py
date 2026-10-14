from typing import TYPE_CHECKING, override

from archinstoo.lib.profile.base import Profile, ProfileType

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class PostgresqlProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'postgresql',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['postgresql-server']

	@property
	@override
	def services(self) -> list[str]:
		return ['postgresql']

	@override
	def post_install(self, install_session: Installer) -> None:
		# postgresql-setup asks systemd for PGDATA, which a chroot has not got;
		# its default is this path
		install_session.arch_chroot('initdb -D /var/lib/pgsql/data', run_as='postgres')
