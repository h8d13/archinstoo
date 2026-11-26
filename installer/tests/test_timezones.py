from typing import TYPE_CHECKING

from archinstoo.lib.localization import catalog

if TYPE_CHECKING:
	from pathlib import Path

	import pytest

# verbatim tzdata rows: zone1970.tab folds NL into Europe/Brussels, zone.tab
# keeps one name per country
ZONE_TAB = (
	'# tzdata comment\n'
	'BE\t+5050+00420\tEurope/Brussels\n'
	'NL\t+5222+00454\tEurope/Amsterdam\n'
	'UA\t+5026+03031\tEurope/Kyiv\tmost of Ukraine\n'
)
ZONE1970_TAB = (
	'# tzdata comment\n'
	'BE,LU,NL\t+5050+00420\tEurope/Brussels\n'
	'UA\t+5026+03031\tEurope/Kyiv\tmost of Ukraine\n'
)


def test_scan_prefers_zone_tab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	(tmp_path / 'zone.tab').write_text(ZONE_TAB)
	(tmp_path / 'zone1970.tab').write_text(ZONE1970_TAB)
	monkeypatch.setenv('TZDIR', str(tmp_path))

	assert catalog._scan_timezones() == [
		'Europe/Amsterdam',
		'Europe/Brussels',
		'Europe/Kyiv',
		'UTC',
	]


def test_scan_falls_back_to_zone1970(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	(tmp_path / 'zone1970.tab').write_text(ZONE1970_TAB)
	monkeypatch.setenv('TZDIR', str(tmp_path))

	assert catalog._scan_timezones() == ['Europe/Brussels', 'Europe/Kyiv', 'UTC']
