# dms and noctalia are full shells (bar, launcher, notifications) on top of a
# compositor: two of them write the same compositor config and both start,
# so a desktop selection holds at most one. Compositors and DEs still stack.
from archinstoo.lib.profile.profiles_handler import ProfileHandler, one_shell


def test_shells_are_typed() -> None:
	handler = ProfileHandler()
	shells = {p.name for p in handler.profiles if p.is_shell_profile()}

	assert {'dms', 'noctalia'} <= shells


def test_config_keeps_first_shell() -> None:
	# the menu hands its picks to the same one_shell()
	profile = ProfileHandler().parse_profile_config(
		{'main': 'desktop', 'details': ['dms', 'noctalia', 'sway']}
	)

	assert profile is not None
	assert [p.name for p in profile.current_selection] == ['dms', 'sway']


def test_single_shell_untouched() -> None:
	handler = ProfileHandler()
	picks = [p for p in handler.profiles if p.name in {'noctalia', 'sway', 'niri'}]

	assert one_shell(picks) == picks
