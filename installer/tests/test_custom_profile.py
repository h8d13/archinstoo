# a profile 'path' is a local python file only: the shipped example loads,
# anything else is reported and never fetched (no remote code run as root)

from pathlib import Path
from typing import Any

import pytest

from archinstoo.lib.models.profile import DisplayServer
from archinstoo.lib.profile import profiles_handler
from archinstoo.lib.profile.profiles_handler import ProfileHandler

EXAMPLE = Path(__file__).parents[1] / 'examples' / 'custom.py'


def test_example_profile_loads() -> None:
	handler = ProfileHandler()
	profile = handler.parse_profile_config(
		{'path': str(EXAMPLE), 'details': ['xfce4']}
	)

	assert profile is not None
	assert profile.name == 'CustomDesktop'
	assert {'vlc', 'neovim'} <= set(profile.packages)
	# exported again on save, by whichever handler serializes it: safe_json
	# does not hold the one that parsed the config
	assert handler.to_json(profile)['path'] == str(EXAMPLE)
	assert ProfileHandler().to_json(profile)['path'] == str(EXAMPLE)


def test_url_path_not_fetched(monkeypatch: pytest.MonkeyPatch) -> None:
	errors: list[str] = []
	monkeypatch.setattr(profiles_handler, 'error', errors.append)

	profile = ProfileHandler().parse_profile_config(
		{'path': 'https://example.org/profile.py'}
	)

	assert profile is None
	assert errors == [
		'Custom profile file not found: https:/example.org/profile.py'
	]


def test_null_sections_of_an_entry_are_empty() -> None:
	# strip_none does not reach into the profiles list: these raised at load
	entry: Any = {'main': 'desktop', 'details': None, 'custom_settings': None}
	profile = ProfileHandler().parse_profile_config(entry)

	assert profile is not None
	assert profile.current_selection == []


@pytest.mark.parametrize(
	'entries',
	[
		[{'main': 'desktop', 'details': ['desktop', 'sway']}],
		[
			{'main': 'desktop', 'details': ['server', 'sway']},
			{'main': 'server', 'details': ['desktop', 'sshd']},
		],
	],
	ids=['under itself', 'under each other'],
)
def test_a_main_is_no_selection(entries: Any) -> None:  # noqa: ANN401
	# either recursed in every walk of the selection, after pacstrap
	config = ProfileHandler().parse_config({'profiles': entries})

	assert DisplayServer.Wayland in config.display_servers()
	# no profile is reached again from its own selection
	for profile in config.profiles:
		below = list(profile.current_selection)
		while below:
			sub = below.pop()
			assert sub is not profile
			below.extend(sub.current_selection)
