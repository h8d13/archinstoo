# dms/noctalia take their compositor from the menu or from a hand-written
# config, and every consumer (packages, provision, binds/config paths) indexes
# a dict by it. These lock the filtering that keeps an unknown name harmless.

import pytest

from archinstoo.default_profiles.desktops.dms import DmsProfile
from archinstoo.default_profiles.desktops.noctalia import NoctaliaProfile

_COMPOSITOR_PROFILES = [(DmsProfile, 'dms_compositor'), (NoctaliaProfile, 'noctalia_compositor')]


@pytest.mark.parametrize(('profile_cls', 'key'), _COMPOSITOR_PROFILES)
@pytest.mark.parametrize('setting', [None, [], '', 'bogus', ['bogus'], ['niri', 'bogus']])
def test_unusable_setting_leaves_a_runnable_compositor(
	profile_cls: type[DmsProfile | NoctaliaProfile],
	key: str,
	setting: str | list[str] | None,
) -> None:
	profile = profile_cls()
	profile.custom_settings[key] = setting

	# something has to run, and only names the packages map knows survive:
	# compositor_packages[comp] is an unguarded lookup on every consumer
	assert profile.compositors
	assert set(profile.compositors) <= set(profile.compositor_packages)
	assert profile.packages


@pytest.mark.parametrize(('profile_cls', 'key'), _COMPOSITOR_PROFILES)
def test_known_selection_is_kept_whole(profile_cls: type[DmsProfile | NoctaliaProfile], key: str) -> None:
	profile = profile_cls()
	profile.custom_settings[key] = ['hyprland', 'niri']

	assert profile.compositors == ['hyprland', 'niri']
