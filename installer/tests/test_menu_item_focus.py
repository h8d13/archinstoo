# focus_item can point at an item that is not in the current items view:
# set_filter_pattern() rebuilds the view and focus_first() leaves the stale
# focus in place when nothing in the new view is selectable. Arrow keys then
# hit _find_next_selectable_item, which must not blow up on the lookup.

from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup


def _group() -> MenuItemGroup:
	return MenuItemGroup([MenuItem('alpha', value='a'), MenuItem('beta', value='b'), MenuItem('gamma', value='g')])


def test_focus_next_recovers_from_stale_focus() -> None:
	group = _group()
	group.focus_item = MenuItem('orphan', value='o')

	group.focus_next()

	assert group.focus_item is group.items[0]


def test_focus_prev_recovers_from_stale_focus() -> None:
	group = _group()
	group.focus_item = MenuItem('orphan', value='o')

	group.focus_prev()

	assert group.focus_item is group.items[-1]


def test_focus_survives_filter_with_no_matches() -> None:
	group = _group()
	group.set_filter_pattern('zzz')

	group.focus_next()
	group.focus_prev()

	assert group.focus_item is not None
