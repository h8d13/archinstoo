from pathlib import Path
from typing import TYPE_CHECKING, Literal, overload

from .curses_menu import EditMenu, SelectMenu
from .menu_item import MenuItem, MenuItemGroup
from .result import ResultType
from .types import Alignment, Orientation

if TYPE_CHECKING:
	from collections.abc import Callable


@overload
def prompt_yes_no(header: str, preset: bool | None = ..., *, allow_skip: Literal[False], default: bool | None = ...) -> bool: ...
@overload
def prompt_yes_no(header: str, preset: bool | None = ..., *, allow_skip: Literal[True] = ..., default: bool | None = ...) -> bool | None: ...


def prompt_yes_no(header: str, preset: bool | None = None, *, allow_skip: bool = True, default: bool | None = None) -> bool | None:
	# the two-button question. preset is where the cursor starts, default the
	# marked answer; None back is a skip, so the caller keeps what it had
	group = MenuItemGroup.yes_no()
	if default is not None:
		group.set_default_by_value(default)
	if preset is not None:
		group.set_focus_by_value(preset)

	result = SelectMenu[bool](
		group,
		header=header,
		alignment=Alignment.CENTER,
		columns=2,
		orientation=Orientation.HORIZONTAL,
		search_enabled=False,
		allow_skip=allow_skip,
	).run()

	if result.type_ == ResultType.Skip:
		return None
	return result.item() == MenuItem.yes()


def prompt_text(
	title: str,
	header: str | None = None,
	preset: str | None = None,
	validator: Callable[[str | None], str | None] | None = None,
	*,
	allow_skip: bool = True,
) -> str | None:
	# one line of input. None back is a skip; an empty entry comes back as ''
	# so the caller decides what empty means
	result = EditMenu(
		title,
		header=header,
		validator=validator,
		allow_skip=allow_skip,
		default_text=preset or None,
	).input()

	if result.type_ == ResultType.Skip:
		return None
	return result.text()


def confirm_abort() -> None:
	if prompt_yes_no('Do you really want to abort?' + '\n', allow_skip=False):
		raise SystemExit(0)


def prompt_dir(
	text: str,
	header: str | None = None,
	validate: bool = True,
	must_exist: bool = True,
	allow_skip: bool = False,
	preset: str | None = None,
) -> Path | None:
	def validate_path(path: str | None) -> str | None:
		if path:
			dest_path = Path(path)

			if must_exist:
				if dest_path.exists() and dest_path.is_dir():
					return None
			else:
				return None

		return 'Not a valid directory'

	path = prompt_text(text, header, preset, validate_path if validate else None, allow_skip=allow_skip)
	return Path(path) if path else None
