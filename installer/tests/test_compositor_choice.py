# dms/noctalia take one compositor from the menu, and the profile and the
# resolver have to agree on what it installs.

from typing import TYPE_CHECKING

import pytest

from archinstoo.default_profiles.desktops.dms import DmsProfile
from archinstoo.default_profiles.desktops.noctalia import NoctaliaProfile
from archinstoo.lib.installer import Installer
from archinstoo.lib.models.users import User
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.scripts._resolve import _profile_packages

if TYPE_CHECKING:
	from pathlib import Path

_COMPOSITOR_PROFILES = [DmsProfile, NoctaliaProfile]

# every (profile, compositor) pair the menu offers
_CHOICES = [(cls, c) for cls in _COMPOSITOR_PROFILES for c in cls.compositor_packages]
_IDS = [f'{cls.__name__}-{c}' for cls, c in _CHOICES]


@pytest.mark.parametrize('profile_cls', _COMPOSITOR_PROFILES)
def test_known_compositor_is_kept_alone(
	profile_cls: type[DmsProfile | NoctaliaProfile],
) -> None:
	profile = profile_cls()
	profile.custom_settings[f'{profile.name}_compositor'] = 'hyprland'

	assert profile.compositor == 'hyprland'
	assert set(profile.compositor_packages['hyprland']) <= set(profile.packages)
	assert 'niri' not in profile.packages


@pytest.mark.parametrize(('profile_cls', 'setting'), _CHOICES, ids=_IDS)
def test_resolver_agrees_with_profile(
	profile_cls: type[DmsProfile | NoctaliaProfile], setting: str
) -> None:
	# scripts count expands a saved config without the runtime profile
	profile = profile_cls()
	key = f'{profile.name}_compositor'
	profile.custom_settings[key] = setting

	assert _profile_packages(profile.name, {key: setting}) == set(profile.packages)


@pytest.mark.parametrize('name', ['dms', 'noctalia'])
@pytest.mark.parametrize(
	'settings',
	[
		{'excluded_packages': ['niri']},
		{'seat_access': 'seatd'},
		# unset, the way a saved config spells it
		{'{name}_compositor': None},
		{'{name}_compositor': ''},
	],
	ids=str,
)
def test_config_settings_keep_the_default_compositor(
	name: str, settings: dict[str, str | list[str] | None]
) -> None:
	# the config's settings replaced the profile's own, and its packages
	# raised KeyError on the compositor halfway through the install
	given = {key.format(name=name): value for key, value in settings.items()}
	profile = ProfileHandler().parse_profile_config(
		{'main': 'desktop', 'details': [name], 'custom_settings': {name: given}}
	)
	assert profile is not None
	(shell,) = profile.current_selection

	assert shell.compositor == 'niri'
	assert set(shell.compositor_packages['niri']) <= set(shell.packages)
	# what the config did set is kept
	for key, value in given.items():
		if value:
			assert shell.custom_settings[key] == value


@pytest.mark.parametrize('compositor', list(DmsProfile.compositor_packages))
def test_dms_shell_starts_once(
	compositor: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	# `dms setup` wants dms.service from the compositor unit, or falls back
	# to starting it from the config: a global enable on top doubles it
	calls: list[list[str]] = []
	session = Installer.__new__(Installer)
	session.target = tmp_path

	def chroot(cmd: list[str], **_: object) -> None:
		calls.append(cmd)

	monkeypatch.setattr(session, 'arch_chroot', chroot, raising=False)

	profile = DmsProfile()
	profile.custom_settings['dms_compositor'] = compositor
	profile.provision(session, [User('ada', None, False)])

	assert not any(cmd[:1] == ['systemctl'] for cmd in calls)
	assert any(cmd[:2] == ['dms', 'setup'] and compositor in cmd for cmd in calls)
