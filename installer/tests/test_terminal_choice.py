# A terminal choice is a package plus TERMINAL in /etc/environment, nothing
# more: shipped WM configs keep their upstream terminal and the profile
# installs it, only our own noctalia assets launch $TERMINAL.

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from archinstoo.default_profiles.desktops import noctalia
from archinstoo.default_profiles.desktops.awesome import AwesomeProfile
from archinstoo.default_profiles.desktops.noctalia import NoctaliaProfile
from archinstoo.default_profiles.desktops.qtile import QtileProfile
from archinstoo.default_profiles.desktops.river import RiverProfile
from archinstoo.lib import args
from archinstoo.lib.applications.cat.terminal import TerminalApp
from archinstoo.lib.installer import Installer
from archinstoo.lib.models.applications import DEFAULT_TERMINAL, ApplicationConfiguration, Terminal, TerminalConfiguration
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


def test_write_environment_replaces_in_place(tmp_path: Path) -> None:
	# a key the caller owns is rewritten where it stands: no duplicate line,
	# and no stale value surviving a second pass (a rerun writes it again)
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
	shipped = tmp_path / 'usr/share/river-classic/example/init'
	shipped.parent.mkdir(parents=True)
	shipped.write_text('#!/bin/sh\nriverctl map normal Super+Shift Return spawn foot\n')
	(tmp_path / 'home/ada').mkdir(parents=True)

	RiverProfile().provision(_session(tmp_path, monkeypatch), [User('ada', None, False)])

	init = tmp_path / 'home/ada/.config/river/init'
	assert init.read_text() == shipped.read_text(), 'the shipped init is copied as is'
	assert init.stat().st_mode & 0o111, 'river skips a non-executable init'


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

	return xinitrc


def test_awesome_starts_from_a_user_xinitrc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# no greeter in this profile, so startx is the way in and ~/.xinitrc wins
	# over the packaged session
	shipped = _awesome_target(tmp_path)

	AwesomeProfile().provision(_session(tmp_path, monkeypatch), [User('ada', None, False)])

	assert (tmp_path / 'home/ada/.xinitrc').read_text() == 'exec awesome\n'
	assert shipped.read_text() == _STOCK_XINITRC, 'the packaged xinitrc must be left alone'


_SHIPPED_TERMINAL = {
	'i3-wm': None,
	'qtile': None,
	'labwc': None,
	'noctalia': None,
	'niri': 'alacritty',
	'dms': 'alacritty',
	'hyprland': 'kitty',
	'sway': 'foot',
	'river': 'foot',
	'mangowm': 'foot',
	'awesome': 'xterm',
}
_TERMINALS = {'ghostty', 'alacritty', 'foot', 'kitty', 'xterm'}


@pytest.mark.parametrize(('name', 'shipped'), _SHIPPED_TERMINAL.items())
def test_profiles_ship_the_terminal_their_config_launches(name: str, shipped: str | None) -> None:
	profile: Profile = next(p for p in ProfileHandler().profiles if p.name == name)

	assert profile.needs_terminal
	assert _TERMINALS & set(profile.packages) == ({shipped} if shipped else set())


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


@pytest.mark.parametrize('compositor', list(NoctaliaProfile.compositor_packages))
def test_noctalia_assets_launch_the_exported_terminal(compositor: str) -> None:
	assets = Path(noctalia.__file__).parent / 'noctalia_assets' / compositor
	text = ''.join(f.read_text() for f in assets.iterdir())

	assert '$TERMINAL' in text
	assert '{{' not in text, 'leftover template placeholder'
