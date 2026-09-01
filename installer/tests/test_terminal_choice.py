# The three routes a terminal choice takes to a profile are documented in
# default_profiles/desktops/__init__.py; these lock the ends of each one.

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from archinstoo.default_profiles.desktops import DEFAULT_TERMINAL, swap_terminal, terminal_command
from archinstoo.default_profiles.desktops.hyprland import HyprlandProfile
from archinstoo.default_profiles.desktops.niri import NiriProfile
from archinstoo.default_profiles.desktops.sway import SwayProfile
from archinstoo.lib import args
from archinstoo.lib.applications.cat.terminal import TerminalApp
from archinstoo.lib.installer import Installer
from archinstoo.lib.models.application import ApplicationConfiguration, Terminal, TerminalConfiguration
from archinstoo.lib.models.users import User
from archinstoo.lib.profile.profiles_handler import ProfileHandler

if TYPE_CHECKING:
	from archinstoo.lib.profile.base import Profile


def _pin_terminal(monkeypatch: pytest.MonkeyPatch, terminal: Terminal | None) -> None:
	app_config = ApplicationConfiguration()
	if terminal is not None:
		app_config.terminal_config = TerminalConfiguration(terminal=terminal)

	handler = SimpleNamespace(config=SimpleNamespace(app_config=app_config))
	monkeypatch.setattr(args._ArchConfigHandlerHolder, 'instance', handler)


def _session(target: Path, monkeypatch: pytest.MonkeyPatch) -> Installer:
	installation = Installer.__new__(Installer)
	installation.target = target
	monkeypatch.setattr(installation, 'arch_chroot', lambda cmd: None, raising=False)
	monkeypatch.setattr(installation, 'add_additional_packages', lambda pkgs: None, raising=False)
	return installation


def test_terminal_command_takes_the_choice(monkeypatch: pytest.MonkeyPatch) -> None:
	_pin_terminal(monkeypatch, Terminal.GHOSTTY)

	assert terminal_command() == 'ghostty'


def test_terminal_command_falls_back_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
	# skipping the menu entry has to leave every profile with a terminal
	_pin_terminal(monkeypatch, None)

	assert terminal_command() == DEFAULT_TERMINAL


def test_swap_terminal_repoints_the_binary(monkeypatch: pytest.MonkeyPatch) -> None:
	_pin_terminal(monkeypatch, Terminal.FOOT)

	assert swap_terminal('set $term alacritty\n', 'alacritty', Path('rc')) == 'set $term foot\n'


def test_swap_terminal_leaves_an_unknown_config_alone(monkeypatch: pytest.MonkeyPatch) -> None:
	# upstream renamed its default: better a stale binding than a mangled config
	_pin_terminal(monkeypatch, Terminal.FOOT)

	assert swap_terminal('set $term wezterm\n', 'alacritty', Path('rc')) == 'set $term wezterm\n'


def test_set_environment_appends_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	(tmp_path / 'etc').mkdir()
	(tmp_path / 'etc/environment').write_text('EDITOR=nano\n')
	installation = _session(tmp_path, monkeypatch)

	installation.set_environment({'TERMINAL': 'foot'})
	installation.set_environment({'TERMINAL': 'kitty', 'LANG': 'C'})

	assert (tmp_path / 'etc/environment').read_text() == 'EDITOR=nano\nTERMINAL=foot\nLANG=C\n'


def test_terminal_app_installs_and_exports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	(tmp_path / 'etc').mkdir()
	installation = _session(tmp_path, monkeypatch)

	installed: list[list[str]] = []
	monkeypatch.setattr(installation, 'add_additional_packages', installed.append, raising=False)

	TerminalApp().install(installation, TerminalConfiguration(terminal=Terminal.KONSOLE))

	assert installed == [['konsole']]
	assert (tmp_path / 'etc/environment').read_text() == 'TERMINAL=konsole\n'


def test_sway_repoints_the_shipped_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	_pin_terminal(monkeypatch, Terminal.KITTY)
	(tmp_path / 'etc/sway').mkdir(parents=True)
	(tmp_path / 'etc/sway/config').write_text('set $term foot\nbindsym $mod+Return exec $term\n')

	SwayProfile().install(_session(tmp_path, monkeypatch))

	assert (tmp_path / 'etc/sway/config').read_text() == 'set $term kitty\nbindsym $mod+Return exec $term\n'


def test_sway_survives_a_missing_shipped_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# a missing /etc/sway/config is sway's problem, not a reason to fail the install
	_pin_terminal(monkeypatch, Terminal.KITTY)

	SwayProfile().install(_session(tmp_path, monkeypatch))

	assert not (tmp_path / 'etc/sway').exists()


def test_hyprland_writes_the_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	_pin_terminal(monkeypatch, Terminal.WEZTERM)
	(tmp_path / 'usr/share/hypr').mkdir(parents=True)
	(tmp_path / 'usr/share/hypr/hyprland.lua').write_text('local terminal    = "kitty"\n')
	(tmp_path / 'home/ada').mkdir(parents=True)

	HyprlandProfile().provision(_session(tmp_path, monkeypatch), [User('ada', None, False)])

	assert (tmp_path / 'home/ada/.config/hypr/hyprland.lua').read_text() == 'local terminal    = "wezterm"\n'


def test_niri_writes_the_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	_pin_terminal(monkeypatch, Terminal.FOOT)
	(tmp_path / 'usr/share/doc/niri').mkdir(parents=True)
	(tmp_path / 'usr/share/doc/niri/default-config.kdl').write_text('Mod+T { spawn "alacritty"; }\n')
	(tmp_path / 'home/ada').mkdir(parents=True)

	NiriProfile().provision(_session(tmp_path, monkeypatch), [User('ada', None, False)])

	assert (tmp_path / 'home/ada/.config/niri/config.kdl').read_text() == 'Mod+T { spawn "foot"; }\n'


def test_niri_survives_a_missing_shipped_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# niri still writes its own on first run, so this is a warning, not a failure
	_pin_terminal(monkeypatch, Terminal.FOOT)
	(tmp_path / 'home/ada').mkdir(parents=True)

	NiriProfile().provision(_session(tmp_path, monkeypatch), [User('ada', None, False)])

	assert not (tmp_path / 'home/ada/.config').exists()


_TERMINAL_PROFILES = ('i3-wm', 'qtile', 'labwc', 'river', 'sway', 'hyprland', 'niri', 'awesome', 'dms', 'noctalia')


@pytest.mark.parametrize('name', _TERMINAL_PROFILES)
def test_profile_packages_follow_the_choice(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
	_pin_terminal(monkeypatch, Terminal.GHOSTTY)

	profile: Profile = next(p for p in ProfileHandler().profiles if p.name == name)
	packages = profile.packages

	assert 'ghostty' in packages
	assert not {'alacritty', 'foot', 'kitty', 'xterm'} & set(packages), f'{name} still hardcodes a terminal'
