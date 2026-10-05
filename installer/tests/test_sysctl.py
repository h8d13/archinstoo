from types import SimpleNamespace
from typing import TYPE_CHECKING

from archinstoo.lib.kernel.sysctl import setup_sysctl
from archinstoo.lib.kernel.zram import setup_zram
from archinstoo.lib.models.swap import ZramAlgorithm
from archinstoo.lib.models.sysctl import (
	BASE_DEFAULTS,
	DEFAULTS_CONF,
	ENTRIES_CONF,
	ZRAM_CONF,
	ZRAM_DEFAULTS,
	SysctlConfiguration,
	sysctl_entries,
)

if TYPE_CHECKING:
	from pathlib import Path


def _drop_ins(target: Path) -> dict[str, list[str]]:
	sysctl_dir = target / 'etc/sysctl.d'
	if not sysctl_dir.is_dir():
		return {}
	return {p.stem: p.read_text().splitlines() for p in sorted(sysctl_dir.iterdir())}


def test_optimized_defaults_get_their_own_drop_in(tmp_path: Path) -> None:
	setup_sysctl(tmp_path, SysctlConfiguration(optimized=True, entries=('vm.swappiness = 10',)))

	assert _drop_ins(tmp_path) == {
		DEFAULTS_CONF: list(BASE_DEFAULTS),
		ENTRIES_CONF: ['vm.swappiness = 10'],
	}


def test_stock_config_writes_nothing(tmp_path: Path) -> None:
	setup_sysctl(tmp_path, SysctlConfiguration())
	assert _drop_ins(tmp_path) == {}


def test_user_entries_apply_last() -> None:
	# sysctl.d applies drop-ins in lexical order, the last write wins
	assert max(ENTRIES_CONF, DEFAULTS_CONF, ZRAM_CONF) == ENTRIES_CONF


def test_zram_setup_ships_its_tuning(tmp_path: Path) -> None:
	(tmp_path / 'etc/systemd').mkdir(parents=True)
	installation = SimpleNamespace(
		target=tmp_path,
		pacman=SimpleNamespace(strap=lambda _pkgs: None),
		enable_service=lambda _unit: None,
	)

	setup_zram(installation, ZramAlgorithm.Default, None)  # type: ignore[arg-type]

	zram = sysctl_entries(_drop_ins(tmp_path)[ZRAM_CONF])
	assert zram['vm.swappiness'] == '180'


def test_parse_arg_round_trip() -> None:
	config = SysctlConfiguration(optimized=True, entries=('kernel.kptr_restrict = 1',))
	assert SysctlConfiguration.parse_arg({'optimized': True, 'entries': ['kernel.kptr_restrict = 1']}) == config
	assert SysctlConfiguration.parse_arg({}) == SysctlConfiguration()


def test_no_duplicate_keys() -> None:
	# defaults and zram drop-ins compose, neither may silently override the other
	lines = [*ZRAM_DEFAULTS, *BASE_DEFAULTS]
	keys = [line.partition('=')[0].strip() for line in lines if line and not line.startswith('#')]
	assert len(keys) == len(set(keys)), sorted(k for k in keys if keys.count(k) > 1)


def test_every_entry_is_key_value() -> None:
	for line in [*ZRAM_DEFAULTS, *BASE_DEFAULTS]:
		if not line or line.startswith('#'):
			continue
		key, sep, value = line.partition(' = ')
		assert sep, line
		assert key, line
		assert value, line
		assert '.' in key, line
		assert key == key.strip(), line
		assert value == value.strip(), line
