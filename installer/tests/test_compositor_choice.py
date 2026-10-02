# dms/noctalia take one compositor from the menu, and the profile and the
# resolver have to agree on what it installs.

import pytest

from archinstoo.default_profiles.desktops.dms import DmsProfile
from archinstoo.default_profiles.desktops.noctalia import NoctaliaProfile
from archinstoo.scripts._resolve import _profile_packages

_COMPOSITOR_PROFILES = [DmsProfile, NoctaliaProfile]


@pytest.mark.parametrize('profile_cls', _COMPOSITOR_PROFILES)
def test_known_compositor_is_kept_alone(profile_cls: type[DmsProfile | NoctaliaProfile]) -> None:
	profile = profile_cls()
	profile.custom_settings[f'{profile.name}_compositor'] = 'hyprland'

	assert profile.compositor == 'hyprland'
	assert set(profile.compositor_packages['hyprland']) <= set(profile.packages)
	assert 'niri' not in profile.packages


@pytest.mark.parametrize('profile_cls', _COMPOSITOR_PROFILES)
@pytest.mark.parametrize('setting', ['niri', 'hyprland'])
def test_resolver_agrees_with_profile(profile_cls: type[DmsProfile | NoctaliaProfile], setting: str) -> None:
	# scripts count expands a saved config without the runtime profile
	profile = profile_cls()
	key = f'{profile.name}_compositor'
	profile.custom_settings[key] = setting

	assert _profile_packages(profile.name, {key: setting}) == set(profile.packages)
