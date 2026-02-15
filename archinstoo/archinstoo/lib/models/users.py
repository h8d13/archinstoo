from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from typing import NotRequired, Self, TypedDict, override

from archinstoo.lib.authentication.crypt import crypt_yescrypt
from archinstoo.lib.translationhandler import tr


class Shell(StrEnum):
	BASH = auto()
	ZSH = auto()
	FISH = auto()
	RBASH = auto()


class SupplementaryGroup(StrEnum):
	"""Common supplementary groups.

	wheel is excluded — auto-added for elevated users.
	audio/video/storage/input/network are excluded —
	device access handled by systemd-logind for active sessions,
	seat management by the seat_access choice (polkit/seatd).
	"""

	ADM = auto()  # read access to protected logs / journal
	FTP = auto()  # access to FTP served files
	GAMES = auto()  # access to some game software
	HTTP = auto()  # access to HTTP served files
	LOG = auto()  # access to /var/log/ (syslog-ng)
	LP = auto()  # printer access
	RFKILL = auto()  # wireless device power control
	SYS = auto()  # administer printers in CUPS
	SYSTEMD_JOURNAL = 'systemd-journal'  # read-only systemd logs
	UUCP = auto()  # serial ports and connected devices


class PasswordStrength(Enum):
	WEAK = 'weak'
	MODERATE = 'moderate'
	STRONG = 'strong'

	@property
	@override
	def value(self) -> str:  # pylint: disable=invalid-overridden-method
		match self:
			case PasswordStrength.WEAK:
				return tr('weak')
			case PasswordStrength.MODERATE:
				return tr('moderate')
			case PasswordStrength.STRONG:
				return tr('strong')

	@classmethod
	def strength(cls, password: str) -> Self:
		digit = any(character.isdigit() for character in password)
		upper = any(character.isupper() for character in password)
		lower = any(character.islower() for character in password)
		symbol = any(not character.isalnum() for character in password)
		return cls._check_password_strength(digit, upper, lower, symbol, len(password))

	@classmethod
	def _check_password_strength(
		cls,
		digit: bool,
		upper: bool,
		lower: bool,
		symbol: bool,
		length: int,
	) -> Self:
		# suggested evaluation
		# https://github.com/archlinux/archinstall/issues/1304#issuecomment-1146768163
		if digit and upper and lower and symbol:
			match length:
				case num if num >= 13:
					return cls.STRONG
				case num if 11 <= num <= 12:
					return cls.MODERATE
				case num if 7 <= num <= 10:
					return cls.WEAK
		elif digit and upper and lower:
			match length:
				case num if num >= 14:
					return cls.STRONG
				case num if 11 <= num <= 13:
					return cls.MODERATE
				case num if 7 <= num <= 10:
					return cls.WEAK
		elif upper and lower:
			match length:
				case num if num >= 15:
					return cls.STRONG
				case num if 12 <= num <= 14:
					return cls.MODERATE
				case num if 7 <= num <= 11:
					return cls.WEAK
		elif lower or upper:
			match length:
				case num if num >= 18:
					return cls.STRONG
				case num if 14 <= num <= 17:
					return cls.MODERATE
				case num if 9 <= num <= 13:
					return cls.WEAK

		return cls.WEAK


class UserSerialization(TypedDict):
	username: str
	elev: bool
	groups: list[str]
	enc_password: str | None
	stash_urls: NotRequired[list[str]]
	shell: NotRequired[str]


class Password:
	def __init__(
		self,
		plaintext: str = '',
		enc_password: str | None = None,
	):
		if plaintext:
			enc_password = crypt_yescrypt(plaintext)

		if not plaintext and not enc_password:
			raise ValueError('Either plaintext or enc_password must be provided')

		self._plaintext = plaintext
		self.enc_password = enc_password

	@property
	def plaintext(self) -> str:
		return self._plaintext

	@override
	def __eq__(self, other: object) -> bool:
		if not isinstance(other, Password):
			return NotImplemented
		return self.enc_password == other.enc_password

	def hidden(self) -> str:
		if self._plaintext:
			return '*' * len(self._plaintext)
		return '*' * 8


@dataclass
class User:
	username: str
	password: Password | None
	elev: bool
	groups: list[str] = field(default_factory=list)
	stash_urls: list[str] = field(default_factory=list)
	shell: Shell = Shell.BASH

	@override
	def __str__(self) -> str:
		# safety overwrite to make sure password is not leaked
		return f'User({self.username=}, {self.elev=}, {self.groups=})'

	def table_data(self) -> dict[str, str | bool]:
		return {
			'username': self.username,
			'password': self.password.hidden() if self.password else '-',
			'elev': self.elev,
			'groups': f'{len(self.groups)}/{len(self.groups)}',
			'shell': self.shell.value,
		}

	def json(self) -> UserSerialization:
		return {
			'username': self.username,
			'enc_password': None,
			'elev': self.elev,
			'groups': self.groups,
			'stash_urls': self.stash_urls,
			'shell': self.shell.value,
		}

	@staticmethod
	def any_elevated(users: list[User]) -> bool:
		return any(u.elev and u.password is not None for u in users)

	@classmethod
	def parse_arguments(
		cls,
		args: list[UserSerialization],
	) -> list[Self]:
		users: list[Self] = []

		for entry in args:
			username = entry.get('username')
			if not username:
				continue

			enc_password = entry.get('enc_password')
			password = Password(enc_password=enc_password) if enc_password else None

			user = cls(
				username=username,
				password=password,
				elev=entry.get('elev', False) is True,
				groups=entry.get('groups') or [],
				stash_urls=entry.get('stash_urls', []),
				shell=Shell(entry['shell']) if 'shell' in entry else Shell.BASH,
			)

			users.append(user)

		return users
