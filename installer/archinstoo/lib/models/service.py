from dataclasses import dataclass
from typing import NotRequired, Self, TypedDict


class UserServiceSerialization(TypedDict):
	unit: str
	user: str
	linger: NotRequired[bool]


@dataclass(frozen=True)
class UserService:
	unit: str
	user: str
	linger: bool = False

	def json(self) -> UserServiceSerialization:
		return {
			'unit': self.unit,
			'user': self.user,
			'linger': self.linger,
		}

	@classmethod
	def parse_arg(cls, arg: UserServiceSerialization) -> Self:
		return cls(
			unit=arg['unit'],
			user=arg['user'],
			linger=arg.get('linger', False),
		)
