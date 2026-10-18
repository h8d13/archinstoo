# a profile 'path' is a local python file only: the shipped example loads,
# anything else is reported and never fetched (no remote code run as root)

from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.profile import profiles_handler
from archinstoo.lib.profile.profiles_handler import ProfileHandler

if TYPE_CHECKING:
	import pytest

EXAMPLE = Path(__file__).parents[1] / 'examples' / 'custom.py'


def test_example_profile_loads() -> None:
	handler = ProfileHandler()
	profile = handler.parse_profile_config({'path': str(EXAMPLE), 'details': ['xfce4']})

	assert profile is not None
	assert profile.name == 'CustomDesktop'
	assert {'vlc', 'neovim'} <= set(profile.packages)
	# exported again on save
	assert handler.to_json(profile)['path'] == str(EXAMPLE)


def test_url_path_not_fetched(monkeypatch: pytest.MonkeyPatch) -> None:
	errors: list[str] = []
	monkeypatch.setattr(profiles_handler, 'error', errors.append)

	profile = ProfileHandler().parse_profile_config({'path': 'https://example.org/profile.py'})

	assert profile is None
	assert errors == ['Custom profile file not found: https:/example.org/profile.py']
