from dataclasses import dataclass
from enum import Enum, auto
from typing import cast

from .menu_item import MenuItem


class ResultType(Enum):
	Selection = auto()
	Skip = auto()
	Reset = auto()


@dataclass
class Result[ValueT]:
	type_: ResultType
	_item: MenuItem | list[MenuItem] | str | None

	def has_item(self) -> bool:
		return self._item is not None

	def get_value(self) -> ValueT:
		return cast('ValueT', self.item().get_value())

	def get_values(self) -> list[ValueT]:
		return [i.get_value() for i in self.items()]

	def item(self) -> MenuItem:
		if not isinstance(self._item, MenuItem):
			raise RuntimeError(f'Result._item is {type(self._item).__name__}, expected MenuItem')
		return self._item

	def items(self) -> list[MenuItem]:
		if not isinstance(self._item, list):
			raise RuntimeError(f'Result._item is {type(self._item).__name__}, expected list')
		return self._item

	def text(self) -> str:
		if not isinstance(self._item, str):
			raise RuntimeError(f'Result._item is {type(self._item).__name__}, expected str')
		return self._item
