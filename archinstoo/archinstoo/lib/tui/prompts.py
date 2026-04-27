from pathlib import Path

from archinstoo.lib.translationhandler import tr

from .curses_menu import EditMenu, SelectMenu
from .menu_item import MenuItem, MenuItemGroup
from .result import ResultType
from .types import Alignment, Orientation


def confirm_abort() -> None:
	prompt = tr('Do you really want to abort?') + '\n'
	group = MenuItemGroup.yes_no()

	result = SelectMenu[bool](
		group,
		header=prompt,
		allow_skip=False,
		alignment=Alignment.CENTER,
		columns=2,
		orientation=Orientation.HORIZONTAL,
	).run()

	if result.item() == MenuItem.yes():
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

		return tr('Not a valid directory')

	validate_func = validate_path if validate else None

	result = EditMenu(
		text,
		header=header,
		alignment=Alignment.CENTER,
		allow_skip=allow_skip,
		validator=validate_func,
		default_text=preset,
	).input()

	match result.type_:
		case ResultType.Skip:
			return None
		case ResultType.Selection:
			if not result.text():
				return None
			return Path(result.text())

	return None
