from dataclasses import dataclass, field
from typing import NotRequired, Self, TypedDict

from archinstall.lib.models.users import Password, User, UserSerialization


class AuthenticationSerialization(TypedDict):
	lock_root_account: NotRequired[bool]
	root_enc_password: NotRequired[str]
	users: NotRequired[list[UserSerialization]]


@dataclass
class AuthenticationConfiguration:
	root_enc_password: Password | None = None
	users: list[User] = field(default_factory=list)
	lock_root_account: bool = False

	@classmethod
	def parse_arg(cls, args: AuthenticationSerialization) -> Self:
		auth_config = cls()

		if enc_password := args.get('root_enc_password'):
			auth_config.root_enc_password = Password(enc_password=enc_password)

		if lock_root := args.get('lock_root_account'):
			auth_config.lock_root_account = lock_root

		if users := args.get('users'):
			auth_config.users = User.parse_arguments(users)

		return auth_config

	def json(self) -> AuthenticationSerialization:
		config: AuthenticationSerialization = {}

		if self.lock_root_account:
			config['lock_root_account'] = self.lock_root_account

		return config
