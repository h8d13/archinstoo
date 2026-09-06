from pathlib import Path
from typing import TYPE_CHECKING, Literal, overload

from .curses_menu import EditMenu, SelectMenu
from .menu_item import MenuItem, MenuItemGroup
from .result import ResultType
from .types import Alignment, FrameProperties, Orientation

if TYPE_CHECKING:
	from collections.abc import Callable


@overload
def prompt_choice[T](
	items: MenuItemGroup | list[MenuItem],
	preset: T | None = ...,
	*,
	header: str | None = ...,
	frame: str | None = ...,
	default: T | None = ...,
	sort_items: bool = ...,
	allow_skip: Literal[False],
	allow_reset: Literal[False] = ...,
) -> T: ...
@overload
def prompt_choice[T](
	items: MenuItemGroup | list[MenuItem],
	preset: T | None = ...,
	*,
	header: str | None = ...,
	frame: str | None = ...,
	default: T | None = ...,
	sort_items: bool = ...,
	allow_skip: bool = ...,
	allow_reset: bool = ...,
	reset: T | None = ...,
) -> T | None: ...


def prompt_choice[T](
	items: MenuItemGroup | list[MenuItem],
	preset: T | None = None,
	*,
	header: str | None = None,
	frame: str | None = None,
	default: T | None = None,
	sort_items: bool = False,
	allow_skip: bool = True,
	allow_reset: bool = False,
	reset: T | None = None,
) -> T | None:
	# one pick. preset is where the cursor starts and what a skip hands back,
	# reset is what a reset hands back, and an item carrying None comes back
	# as None; so the caller reads the answer, not the result type
	group = items if isinstance(items, MenuItemGroup) else MenuItemGroup(items, sort_items=sort_items)
	if default is not None:
		group.set_default_by_value(default)
	if preset is not None:
		group.set_focus_by_value(preset)

	result = SelectMenu[T](
		group,
		header=header,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(frame) if frame else None,
		allow_skip=allow_skip,
		allow_reset=allow_reset,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return reset
		case ResultType.Selection:
			value: T | None = result.item().value
			return value


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
