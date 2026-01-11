from dataclasses import dataclass, field
from enum import Enum
from typing import NotRequired, Self, TypedDict

from archinstall.lib.models.users import Password, User, UserSerialization
from archinstall.lib.translationhandler import tr


class U2FLoginConfigSerialization(TypedDict):
	u2f_login_method: str
	passwordless_sudo: bool


class AuthenticationSerialization(TypedDict):
	u2f_config: NotRequired[U2FLoginConfigSerialization]
	lock_root_account: NotRequired[bool]
	root_enc_password: NotRequired[str]
	users: NotRequired[list[UserSerialization]]


class U2FLoginMethod(Enum):
	Passwordless = 'passwordless'
	SecondFactor = 'second_factor'

	def display_value(self) -> str:
		match self:
			case U2FLoginMethod.Passwordless:
				return tr('Passwordless login')
			case U2FLoginMethod.SecondFactor:
				return tr('Second factor login')
			case _:
				raise ValueError(f'Unknown type: {self}')


@dataclass
class U2FLoginConfiguration:
	u2f_login_method: U2FLoginMethod
	passwordless_sudo: bool = False

	def json(self) -> U2FLoginConfigSerialization:
		return {
			'u2f_login_method': self.u2f_login_method.value,
			'passwordless_sudo': self.passwordless_sudo,
		}

	@classmethod
	def parse_arg(cls, args: U2FLoginConfigSerialization) -> Self | None:
		u2f_login_method = args.get('u2f_login_method')

		if not u2f_login_method:
			return None

		u2f_config = cls(u2f_login_method=U2FLoginMethod(u2f_login_method))

		u2f_config.u2f_login_method = U2FLoginMethod(u2f_login_method)

		if passwordless_sudo := args.get('passwordless_sudo') is not None:
			u2f_config.passwordless_sudo = passwordless_sudo

		return u2f_config


@dataclass
class AuthenticationConfiguration:
	root_enc_password: Password | None = None
	users: list[User] = field(default_factory=list)
	u2f_config: U2FLoginConfiguration | None = None
	lock_root_account: bool = False

	@classmethod
	def parse_arg(cls, args: AuthenticationSerialization) -> Self:
		auth_config = cls()

		if (u2f_config := args.get('u2f_config')) is not None:
			auth_config.u2f_config = U2FLoginConfiguration.parse_arg(u2f_config)

		if enc_password := args.get('root_enc_password'):
			auth_config.root_enc_password = Password(enc_password=enc_password)

		if lock_root := args.get('lock_root_account'):
			auth_config.lock_root_account = lock_root

		if users := args.get('users'):
			auth_config.users = User.parse_arguments(users)

		return auth_config

	def json(self) -> AuthenticationSerialization:
		config: AuthenticationSerialization = {}

		if self.u2f_config:
			config['u2f_config'] = self.u2f_config.json()

		if self.lock_root_account:
			config['lock_root_account'] = self.lock_root_account

		return config
