from dataclasses import dataclass, field
from enum import Enum
from typing import NotRequired, Self, TypedDict

from archinstall.lib.models.users import Password, User, UserSerialization


class PrivilegeEscalation(Enum):
	Sudo = 'sudo'
	Doas = 'doas'

	def packages(self) -> list[str]:
		return {
			PrivilegeEscalation.Sudo: ['sudo'],
			PrivilegeEscalation.Doas: ['opendoas'],
		}[self]


class AuthenticationSerialization(TypedDict):
	lock_root_account: NotRequired[bool]
	root_enc_password: NotRequired[str]
	users: NotRequired[list[UserSerialization]]
	privilege_escalation: NotRequired[str]


@dataclass
class AuthenticationConfiguration:
	root_enc_password: Password | None = None
	users: list[User] = field(default_factory=list)
	lock_root_account: bool = False
	privilege_escalation: PrivilegeEscalation = PrivilegeEscalation.Sudo

	@classmethod
	def parse_arg(cls, args: AuthenticationSerialization) -> Self:
		auth_config = cls()

		if enc_password := args.get('root_enc_password'):
			auth_config.root_enc_password = Password(enc_password=enc_password)

		if lock_root := args.get('lock_root_account'):
			auth_config.lock_root_account = lock_root

		if users := args.get('users'):
			auth_config.users = User.parse_arguments(users)

		if priv_esc := args.get('privilege_escalation'):
			auth_config.privilege_escalation = PrivilegeEscalation(priv_esc)

		return auth_config

	def json(self) -> AuthenticationSerialization:
		# We keep only these 2 as json
		# Users or pws are never stored
		config: AuthenticationSerialization = {}

		if self.lock_root_account:
			config['lock_root_account'] = self.lock_root_account

		if self.privilege_escalation != PrivilegeEscalation.Sudo:
			config['privilege_escalation'] = self.privilege_escalation.value

		return config
