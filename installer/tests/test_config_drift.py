# examples/ are the reference users copy from: a new config section can
# land in models and schema and never reach them.

import json
import re
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

import archinstoo
from archinstoo.lib.args import ArchConfig
from archinstoo.lib.models.applications import ApplicationConfiguration

EXAMPLES = Path(__file__).parent.parent / 'examples'
FULL = EXAMPLES / 'config_sample_full.json'


def _load(path: Path) -> dict[str, Any]:
	data: dict[str, Any] = json.loads(path.read_text())
	return data


def test_full_example_has_every_top_level_key() -> None:
	expected = set(ArchConfig().safe_json())
	missing = expected - set(_load(FULL))
	assert not missing, (
		f'config_sample_full.json lacks top-level keys: {sorted(missing)}'
	)


def test_full_example_has_every_app_section() -> None:
	expected = set(ApplicationConfiguration._config_parsers())
	missing = expected - set(_load(FULL)['app_config'])
	assert not missing, (
		f'config_sample_full.json lacks app_config sections: {sorted(missing)}'
	)


@pytest.mark.parametrize('path', sorted(EXAMPLES.glob('*.json')), ids=lambda p: p.name)
def test_example_app_config_round_trips(path: Path) -> None:
	# the section is optional: ci_minimal installs no apps at all and names
	# none, which has to stay a valid config. What is declared must still parse
	raw = _load(path).get('app_config')
	if raw is None:
		pytest.skip('no app_config section')
	# parse_arg raises ValueError on an enum value the code no longer knows
	parsed = ApplicationConfiguration.parse_arg(raw)
	assert parsed.json() == raw


def test_global_menu_keys_are_config_fields() -> None:
	# AbstractMenu syncs items by getattr/setattr on ArchConfig: a key that
	# is no field only fails once the menu is on screen
	source = (Path(archinstoo.__file__).parent / 'lib/global_menu.py').read_text()
	keys = set(re.findall(r"(?:key=|find_by_key\()\s*'(\w+)'", source))
	assert keys
	unknown = keys - {f.name for f in fields(ArchConfig)}
	assert not unknown, f'global_menu.py keys ArchConfig lacks: {sorted(unknown)}'
