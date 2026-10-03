# dms/noctalia take one compositor from the menu, and the profile and the
# resolver have to agree on what it installs.

from typing import TYPE_CHECKING

import pytest

from archinstoo.default_profiles.desktops.dms import DmsProfile
from archinstoo.default_profiles.desktops.noctalia import NoctaliaProfile
from archinstoo.lib.installer import Installer
from archinstoo.lib.models.users import User
from archinstoo.scripts._resolve import _profile_packages

if TYPE_CHECKING:
	from pathlib import Path

_COMPOSITOR_PROFILES = [DmsProfile, NoctaliaProfile]

# every (profile, compositor) pair the menu offers
_CHOICES = [(cls, c) for cls in _COMPOSITOR_PROFILES for c in cls.compositor_packages]
_IDS = [f'{cls.__name__}-{c}' for cls, c in _CHOICES]


@pytest.mark.parametrize('profile_cls', _COMPOSITOR_PROFILES)
def test_known_compositor_is_kept_alone(profile_cls: type[DmsProfile | NoctaliaProfile]) -> None:
	profile = profile_cls()
	profile.custom_settings[f'{profile.name}_compositor'] = 'hyprland'

	assert profile.compositor == 'hyprland'
	assert set(profile.compositor_packages['hyprland']) <= set(profile.packages)
	assert 'niri' not in profile.packages


@pytest.mark.parametrize(('profile_cls', 'setting'), _CHOICES, ids=_IDS)
def test_resolver_agrees_with_profile(profile_cls: type[DmsProfile | NoctaliaProfile], setting: str) -> None:
	# scripts count expands a saved config without the runtime profile
	profile = profile_cls()
	key = f'{profile.name}_compositor'
	profile.custom_settings[key] = setting

	assert _profile_packages(profile.name, {key: setting}) == set(profile.packages)


@pytest.mark.parametrize('compositor', list(DmsProfile.compositor_packages))
def test_dms_shell_starts_once(compositor: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# mango-session.target activates graphical-session.target like the others,
	# but `dms setup` gives mango `exec-once=dms run`: enabling dms.service on
	# top would start a second shell
	calls: list[list[str]] = []
	session = Installer.__new__(Installer)
	session.target = tmp_path

	def chroot(cmd: list[str], **_: object) -> None:
		calls.append(cmd)

	monkeypatch.setattr(session, 'arch_chroot', chroot, raising=False)

	profile = DmsProfile()
	profile.custom_settings['dms_compositor'] = compositor
	profile.provision(session, [User('ada', None, False)])

	enabled = ['systemctl', '--global', 'enable', 'dms.service'] in calls
	assert enabled == (compositor != 'mango')
	assert any(cmd[:2] == ['dms', 'setup'] and compositor in cmd for cmd in calls)
