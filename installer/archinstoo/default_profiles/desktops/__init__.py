from archinstoo.lib.profile.base import SeatAccess
from archinstoo.lib.tui.curses_menu import SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.types import Alignment, FrameProperties


def select_seat_access(name: str, default: str | list[str] | None) -> str:
	header = f'{name} needs access to your seat (collection of hardware devices i.e. keyboard, mouse, etc)'
	header += '\n' + f'Choose an option to give {name} access to your hardware' + '\n'

	items = [MenuItem(s.label, value=s) for s in SeatAccess]
	group = MenuItemGroup(items, sort_items=True)
	group.set_default_by_value(default)

	# no skip, no reset: a Selection is the only way out
	return (
		SelectMenu[SeatAccess](
			group,
			header=header,
			allow_skip=False,
			frame=FrameProperties.min('Seat access'),
			alignment=Alignment.CENTER,
		)
		.run()
		.get_value()
		.value
	)


def select_compositor(name: str, options: list[str], default: str) -> str:
	header = f'{name} runs on top of a Wayland compositor' + '\n'

	items = [MenuItem(c, value=c) for c in options]
	group = MenuItemGroup(items, sort_items=True)
	group.set_default_by_value(default)

	# no skip, no reset: a Selection is the only way out
	return (
		SelectMenu[str](
			group,
			header=header,
			allow_skip=False,
			frame=FrameProperties.min('Compositor'),
			alignment=Alignment.CENTER,
		)
		.run()
		.get_value()
	)
