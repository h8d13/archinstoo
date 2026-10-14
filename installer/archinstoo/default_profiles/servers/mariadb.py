from typing import override

from archinstoo.lib.profile.base import Profile, ProfileType


class MariadbProfile(Profile):
	def __init__(self) -> None:
		super().__init__(
			'mariadb',
			ProfileType.ServerType,
		)

	@property
	@override
	def packages(self) -> list[str]:
		return ['mariadb-server']

	@property
	@override
	def services(self) -> list[str]:
		return ['mariadb']

	# no post_install: mariadb.service prepares the data dir on first start
