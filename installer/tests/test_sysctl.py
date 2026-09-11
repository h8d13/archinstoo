# the optimized sysctl preset is what a user loads in the menu and what a
# conformance/bench harness compares the booted guest against, so the list
# has to stay well-formed and the zram block has to track the zram choice
from archinstoo.lib.models.swap import SwapConfiguration
from archinstoo.lib.models.sysctl import sysctl_defaults, sysctl_entries

ZRAM_KEYS = {'vm.swappiness', 'vm.watermark_boost_factor', 'vm.watermark_scale_factor', 'vm.page-cluster'}


def test_zram_block_follows_zram_not_swap_enabled() -> None:
	with_zram = sysctl_entries(sysctl_defaults(SwapConfiguration(zram=True, hibernation=False)))
	assert with_zram.keys() >= ZRAM_KEYS
	assert with_zram['vm.swappiness'] == '180'

	# hibernation alone is a disk-backed swap file: swappiness 180 would be wrong
	file_only = sysctl_entries(sysctl_defaults(SwapConfiguration(zram=False, hibernation=True)))
	assert not ZRAM_KEYS & file_only.keys()

	assert not ZRAM_KEYS & sysctl_entries(sysctl_defaults(None)).keys()


def test_no_duplicate_keys() -> None:
	lines = sysctl_defaults(SwapConfiguration())
	keys = [line.partition('=')[0].strip() for line in lines if line and not line.startswith('#')]
	assert len(keys) == len(set(keys)), sorted(k for k in keys if keys.count(k) > 1)


def test_every_entry_is_key_value() -> None:
	for line in sysctl_defaults(SwapConfiguration()):
		if not line or line.startswith('#'):
			continue
		key, sep, value = line.partition(' = ')
		assert sep, line
		assert key, line
		assert value, line
		assert '.' in key, line
		assert key == key.strip(), line
		assert value == value.strip(), line
