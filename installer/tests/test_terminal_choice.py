# The three routes a terminal choice takes to a profile are documented in
# default_profiles/desktops/__init__.py; these lock the ends of each one.

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from archinstoo.default_profiles.desktops import swap_terminal, terminal_command
from archinstoo.default_profiles.desktops.awesome import AwesomeProfile
from archinstoo.default_profiles.desktops.hyprland import HyprlandProfile
from archinstoo.default_profiles.desktops.niri import NiriProfile
from archinstoo.default_profiles.desktops.qtile import QtileProfile
from archinstoo.default_profiles.desktops.river import RiverProfile
from archinstoo.default_profiles.desktops.sway import SwayProfile
from archinstoo.lib import args
from archinstoo.lib.applications.cat.terminal import TerminalApp
from archinstoo.lib.installer import Installer
from archinstoo.lib.models.application import DEFAULT_TERMINAL, ApplicationConfiguration, Terminal, TerminalConfiguration
from archinstoo.lib.models.users import User
from archinstoo.lib.profile.config import ProfileConfiguration
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.lib.sysconfig import write_environment

if TYPE_CHECKING:
	from archinstoo.lib.profile.base import Profile


def _pin_terminal(monkeypatch: pytest.MonkeyPatch, terminal: Terminal | None) -> ApplicationConfiguration:
	app_config = ApplicationConfiguration()
	if terminal is not None:
		app_config.terminal_config = TerminalConfiguration(terminal=terminal)

	handler = SimpleNamespace(config=SimpleNamespace(app_config=app_config))
	monkeypatch.setattr(args._ArchConfigHandlerHolder, 'instance', handler)
	return app_config


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


def test_write_environment_replaces_in_place(tmp_path: Path) -> None:
	# a key the caller owns is rewritten where it stands: no duplicate line,
	# and no stale value surviving a second pass (live mode writes /etc twice)
	(tmp_path / 'etc').mkdir()
	(tmp_path / 'etc/environment').write_text('EDITOR=nano\n')

	write_environment(tmp_path, {'TERMINAL': 'foot'})
	write_environment(tmp_path, {'TERMINAL': 'kitty', 'LANG': 'C'})

	assert (tmp_path / 'etc/environment').read_text() == 'EDITOR=nano\nTERMINAL=kitty\nLANG=C\n'


def test_write_environment_leaves_unclaimed_lines_alone(tmp_path: Path) -> None:
	(tmp_path / 'etc').mkdir()
	(tmp_path / 'etc/environment').write_text('# set by hand\nEDITOR=nano\nXKB_DEFAULT_LAYOUT=be\n')

	write_environment(tmp_path, {'XKB_DEFAULT_LAYOUT': 'de'})

	assert (tmp_path / 'etc/environment').read_text() == '# set by hand\nEDITOR=nano\nXKB_DEFAULT_LAYOUT=de\n'


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


def test_qtile_writes_the_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# guess_terminal() takes a preference before its own list, so the pick is
	# passed in rather than replacing the call
	_pin_terminal(monkeypatch, Terminal.KITTY)
	(tmp_path / 'usr/share/doc/qtile').mkdir(parents=True)
	(tmp_path / 'usr/share/doc/qtile/default_config.py').write_text('terminal = guess_terminal()\n')
	(tmp_path / 'home/ada').mkdir(parents=True)

	QtileProfile().provision(_session(tmp_path, monkeypatch), [User('ada', None, False)])

	assert (tmp_path / 'home/ada/.config/qtile/config.py').read_text() == 'terminal = guess_terminal("kitty")\n'


def test_qtile_preference_covers_a_wayland_only_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# foot is on guess_terminal()'s list only when WAYLAND_DISPLAY is set, and
	# this profile is Xorg: unpreferred it would resolve to None, a dead bind
	_pin_terminal(monkeypatch, Terminal.FOOT)
	(tmp_path / 'usr/share/doc/qtile').mkdir(parents=True)
	(tmp_path / 'usr/share/doc/qtile/default_config.py').write_text('terminal = guess_terminal()\n')
	(tmp_path / 'home/ada').mkdir(parents=True)

	QtileProfile().provision(_session(tmp_path, monkeypatch), [User('ada', None, False)])

	assert (tmp_path / 'home/ada/.config/qtile/config.py').read_text() == 'terminal = guess_terminal("foot")\n'


def test_qtile_survives_a_missing_shipped_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# qtile still loads its built-in copy, so this is a warning, not a failure
	_pin_terminal(monkeypatch, Terminal.KITTY)
	(tmp_path / 'home/ada').mkdir(parents=True)

	QtileProfile().provision(_session(tmp_path, monkeypatch), [User('ada', None, False)])

	assert not (tmp_path / 'home/ada/.config').exists()


def test_qtile_ships_a_scalable_font() -> None:
	# the default config's widget_defaults ask pango for "sans"; nothing in
	# qtile's dep chain pulls a font, and a greeter that does is optional
	assert 'ttf-liberation' in QtileProfile().packages


def test_qtile_ships_xwayland() -> None:
	# the package lists the wayland session entry alongside the X11 one, and
	# that backend refuses to start without an Xwayland binary
	assert 'xorg-xwayland' in QtileProfile().packages


def test_river_writes_an_executable_user_init(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# river runs init as a program and has no /etc fallback: a missing or
	# non-executable copy is a black screen with no bindings
	_pin_terminal(monkeypatch, Terminal.KITTY)
	shipped = tmp_path / 'usr/share/river-classic/example/init'
	shipped.parent.mkdir(parents=True)
	shipped.write_text('#!/bin/sh\nriverctl map normal Super+Shift Return spawn foot\n')
	(tmp_path / 'home/ada').mkdir(parents=True)

	RiverProfile().provision(_session(tmp_path, monkeypatch), [User('ada', None, False)])

	init = tmp_path / 'home/ada/.config/river/init'
	assert init.read_text() == '#!/bin/sh\nriverctl map normal Super+Shift Return spawn kitty\n'
	assert init.stat().st_mode & 0o111, 'river skips a non-executable init'
	assert shipped.read_text() == '#!/bin/sh\nriverctl map normal Super+Shift Return spawn foot\n'


def test_river_installs_classic_not_the_rewrite() -> None:
	# extra/river is the 0.4 compositor without a window manager and none is
	# packaged; river-classic is the line that runs standalone
	packages = RiverProfile().packages

	assert 'river-classic' in packages
	assert 'river' not in packages


# verbatim from xorg-xinit 1.4.4-1: what startx falls back to with no
# ~/.xinitrc. The profile installs none of it and no longer edits it
_STOCK_XINITRC = """\
xclock="xclock"
xterm="xterm"
twm="twm"

"$twm" &
"$xclock" -geometry 50x50-1+1 &
exec "$xterm" -geometry 80x66+0+0 -name login
"""


def _awesome_target(tmp_path: Path) -> Path:
	xinitrc = tmp_path / 'etc/X11/xinit/xinitrc'
	xinitrc.parent.mkdir(parents=True)
	xinitrc.write_text(_STOCK_XINITRC)

	rc_lua = tmp_path / 'etc/xdg/awesome/rc.lua'
	rc_lua.parent.mkdir(parents=True)
	rc_lua.write_text('terminal = "xterm"\n')

	return xinitrc


def test_awesome_starts_from_a_user_xinitrc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# no greeter in this profile, so startx is the way in and ~/.xinitrc wins
	# over the packaged session
	_pin_terminal(monkeypatch, Terminal.FOOT)
	shipped = _awesome_target(tmp_path)

	AwesomeProfile().provision(_session(tmp_path, monkeypatch), [User('ada', None, False)])

	assert (tmp_path / 'home/ada/.xinitrc').read_text() == 'exec awesome\n'
	assert shipped.read_text() == _STOCK_XINITRC, 'the packaged xinitrc must be left alone'


def test_awesome_repoints_the_terminal_in_the_user_rc_lua(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	_pin_terminal(monkeypatch, Terminal.FOOT)
	_awesome_target(tmp_path)

	AwesomeProfile().provision(_session(tmp_path, monkeypatch), [User('ada', None, False)])

	assert (tmp_path / 'home/ada/.config/awesome/rc.lua').read_text() == 'terminal = "foot"\n'
	assert (tmp_path / 'etc/xdg/awesome/rc.lua').read_text() == 'terminal = "xterm"\n'


def test_awesome_still_starts_without_a_shipped_rc_lua(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# rc.lua only carries the terminal; losing it must not cost the exec line
	_pin_terminal(monkeypatch, Terminal.FOOT)

	AwesomeProfile().provision(_session(tmp_path, monkeypatch), [User('ada', None, False)])

	assert (tmp_path / 'home/ada/.xinitrc').read_text() == 'exec awesome\n'
	assert not (tmp_path / 'home/ada/.config').exists()


_TERMINAL_PROFILES = ('i3-wm', 'qtile', 'labwc', 'river', 'sway', 'hyprland', 'niri', 'awesome', 'dms', 'noctalia')


@pytest.mark.parametrize('name', _TERMINAL_PROFILES)
def test_terminal_profiles_ship_no_terminal(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
	# these carry a keybind, not a terminal: install_profile_config() installs
	# the one choice for them, which is what keeps their package list fixed
	_pin_terminal(monkeypatch, Terminal.GHOSTTY)

	profile: Profile = next(p for p in ProfileHandler().profiles if p.name == name)

	assert profile.needs_terminal
	assert not {'ghostty', 'alacritty', 'foot', 'kitty', 'xterm'} & set(profile.packages), f'{name} still carries a terminal'


@pytest.mark.parametrize(('pick', 'expected'), [(Terminal.GHOSTTY, 'ghostty'), (None, DEFAULT_TERMINAL)])
def test_install_adds_the_choice_once(pick: Terminal | None, expected: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# a skipped menu entry still has to leave those profiles with a terminal
	app_config = _pin_terminal(monkeypatch, pick)
	installed: list[str] = []
	session = _session(tmp_path, monkeypatch)
	monkeypatch.setattr(session, 'add_additional_packages', installed.extend, raising=False)

	handler = ProfileHandler()
	sway = next(p for p in handler.profiles if p.name == 'sway')
	handler.install_profile_config(session, ProfileConfiguration(profiles=[sway]), app_config)

	assert installed.count(expected) == 1
