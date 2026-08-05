from dataclasses import dataclass
from typing import Self, TypedDict


class UserServiceSerialization(TypedDict):
	unit: str
	user: str
	linger: bool


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
	def parse_arg(cls, arg: dict[str, object]) -> Self:
		return cls(
			unit=str(arg['unit']),
			user=str(arg['user']),
			linger=bool(arg.get('linger', False)),
		)
