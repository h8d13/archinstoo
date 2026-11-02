# nwg-shell: the package is a metapackage, the per-user installer lays the
# configs down; nwg-hello is its greetd greeter, hosted by sway.
from typing import TYPE_CHECKING

import pytest

from archinstoo.default_profiles.desktops.nwg_shell import NwgShellProfile
from archinstoo.lib.installer import Installer
from archinstoo.lib.models.users import User
from archinstoo.lib.profile import profiles_handler
from archinstoo.lib.profile.base import GreeterType
from archinstoo.lib.profile.profiles_handler import ProfileHandler

if TYPE_CHECKING:
	from pathlib import Path


def _session(target: Path, monkeypatch: pytest.MonkeyPatch) -> Installer:
	session = Installer.__new__(Installer)
	session.target = target
	for name in ('add_additional_packages', 'enable_service', 'disable_service'):
		monkeypatch.setattr(session, name, lambda _: None, raising=False)
	return session


def _provision(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vconsole: str
) -> list[tuple[list[str], str | None]]:
	calls: list[tuple[list[str], str | None]] = []
	session = _session(tmp_path, monkeypatch)

	def chroot(cmd: list[str], run_as: str | None = None) -> None:
		calls.append((cmd, run_as))

	monkeypatch.setattr(session, 'arch_chroot', chroot, raising=False)
	(tmp_path / 'etc').mkdir()
	(tmp_path / 'etc/vconsole.conf').write_text(vconsole)

	users = [User('ada', None, False), User('bob', None, False)]
	NwgShellProfile().provision(session, users)
	return calls


def test_installer_runs_per_user_without_reboot(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	# -w alone ends on `sudo systemctl reboot -f`; -s is what stops it
	calls = _provision(tmp_path, monkeypatch, 'KEYMAP=us\nXKBLAYOUT=us\n')

	assert [run_as for _, run_as in calls] == ['ada', 'bob']
	assert all(cmd[:3] == ['nwg-shell-installer', '-w', '-s'] for cmd, _ in calls)


@pytest.mark.parametrize(
	('vconsole', 'layout'),
	[
		# set_keyboard() keeps the graphical layout next to the console one
		('KEYMAP=be-latin1\nXKBLAYOUT=be\nXKBVARIANT=oss\n', 'be'),
		('KEYMAP=us\nXKBLAYOUT=de,us\n', 'de,us'),
		# no graphical layout picked: libxkbcommon's default, never KEYMAP
		('KEYMAP=be-latin1\n', 'us'),
	],
)
def test_installer_gets_the_xkb_layout(
	vconsole: str,
	layout: str,
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	# left to itself the installer reads localectl's "VC Keymap" (console,
	# e.g. be-latin1) into sway's xkb_layout, which xkbcommon rejects
	calls = _provision(tmp_path, monkeypatch, vconsole)

	assert all(cmd[3:] == ['-k', layout] for cmd, _ in calls)


def test_greeter_follows_seat_access() -> None:
	assert NwgShellProfile().default_greeter_type is GreeterType.NwgHello

	# a graphical greeter holds DRM master at handoff, seatd can't take it
	seatd = NwgShellProfile()
	seatd.custom_settings['seat_access'] = 'seatd'
	assert seatd.default_greeter_type is GreeterType.Ly


def test_nwg_hello_runs_under_sway(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	groups: list[tuple[str, list[str]]] = []
	monkeypatch.setattr(
		profiles_handler,
		'add_to_group',
		lambda _session, group, users: groups.append((group, users)),
	)
	(tmp_path / 'etc/greetd').mkdir(parents=True)

	ProfileHandler().install_greeter(
		_session(tmp_path, monkeypatch), GreeterType.NwgHello
	)

	config = (tmp_path / 'etc/greetd/config.toml').read_text()
	assert 'command = "sway -c /etc/nwg-hello/sway-config"' in config
	assert 'user = "greeter"' in config
	assert groups == [('seat', ['greeter'])]
	assert 'sway' in GreeterType.NwgHello.packages
