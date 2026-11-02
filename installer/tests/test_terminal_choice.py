# A terminal choice is a package plus TERMINAL in /etc/environment, nothing
# more: shipped WM configs keep their upstream terminal and the profile
# installs it, only our own noctalia assets launch $TERMINAL (alacritty
# when unset).

import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from archinstoo.default_profiles.desktops import noctalia
from archinstoo.default_profiles.desktops.awesome import AwesomeProfile
from archinstoo.default_profiles.desktops.noctalia import NoctaliaProfile
from archinstoo.default_profiles.desktops.qtile import QtileProfile
from archinstoo.default_profiles.desktops.river import RiverProfile
from archinstoo.lib.applications.cat.terminal import TerminalApp
from archinstoo.lib.installer import Installer
from archinstoo.lib.models.applications import (
	Terminal,
	TerminalConfiguration,
)
from archinstoo.lib.models.users import User
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.lib.sysconfig import write_environment

if TYPE_CHECKING:
	from archinstoo.lib.profile.base import Profile


def _session(target: Path, monkeypatch: pytest.MonkeyPatch) -> Installer:
	installation = Installer.__new__(Installer)
	installation.target = target
	monkeypatch.setattr(
		installation, 'arch_chroot', lambda cmd: None, raising=False
	)
	monkeypatch.setattr(
		installation,
		'add_additional_packages',
		lambda pkgs: None,
		raising=False,
	)
	return installation


def test_write_environment_replaces_in_place(tmp_path: Path) -> None:
	# a key the caller owns is rewritten where it stands: no duplicate line,
	# and no stale value surviving a second pass (a rerun writes it again)
	(tmp_path / 'etc').mkdir()
	(tmp_path / 'etc/environment').write_text('EDITOR=nano\n')

	write_environment(tmp_path, {'TERMINAL': 'foot'})
	write_environment(tmp_path, {'TERMINAL': 'kitty', 'LANG': 'C'})

	assert (tmp_path / 'etc/environment').read_text() == textwrap.dedent("""\
		EDITOR=nano
		TERMINAL=kitty
		LANG=C
	""")


def test_write_environment_leaves_unclaimed_lines_alone(tmp_path: Path) -> None:
	(tmp_path / 'etc').mkdir()
	(tmp_path / 'etc/environment').write_text(
		textwrap.dedent("""\
			# set by hand
			EDITOR=nano
			XKB_DEFAULT_LAYOUT=be
		""")
	)

	write_environment(tmp_path, {'XKB_DEFAULT_LAYOUT': 'de'})

	assert (tmp_path / 'etc/environment').read_text() == textwrap.dedent("""\
		# set by hand
		EDITOR=nano
		XKB_DEFAULT_LAYOUT=de
	""")


def test_terminal_app_installs_and_exports(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	(tmp_path / 'etc').mkdir()
	installation = _session(tmp_path, monkeypatch)

	installed: list[list[str]] = []
	monkeypatch.setattr(
		installation, 'add_additional_packages', installed.append, raising=False
	)

	TerminalApp().install(
		installation, TerminalConfiguration(terminal=Terminal.KONSOLE)
	)

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


def test_awesome_starts_from_a_user_xinitrc(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	# no greeter in this profile, so startx is the way in and ~/.xinitrc wins
	# over the packaged session
	shipped = _awesome_target(tmp_path)

	AwesomeProfile().provision(
		_session(tmp_path, monkeypatch), [User('ada', None, False)]
	)

	assert (tmp_path / 'home/ada/.xinitrc').read_text() == 'exec awesome\n'
	assert shipped.read_text() == _STOCK_XINITRC, (
		'the packaged xinitrc must be left alone'
	)


_SHIPPED_TERMINAL = {
	# upstream launchers search a list: alacritty is in each of them
	'i3-wm': 'alacritty',
	'qtile': 'alacritty',
	'labwc': 'alacritty',
	'noctalia': 'alacritty',
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
def test_profiles_ship_the_terminal_their_config_launches(
	name: str, shipped: str
) -> None:
	profile: Profile = next(p for p in ProfileHandler().profiles if p.name == name)

	assert _TERMINALS & set(profile.packages) == {shipped}


@pytest.mark.parametrize('compositor', list(NoctaliaProfile.compositor_packages))
def test_noctalia_assets_launch_the_exported_terminal(compositor: str) -> None:
	assets = Path(noctalia.__file__).parent / 'noctalia_assets' / compositor
	text = ''.join(f.read_text() for f in assets.iterdir())

	assert '${TERMINAL:-alacritty}' in text
	assert '{{' not in text, 'leftover template placeholder'
