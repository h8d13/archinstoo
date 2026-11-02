# nwg-shell: the package is a metapackage, the per-user installer lays the
# configs down; nwg-hello is its greetd greeter, hosted by sway.
from typing import TYPE_CHECKING

from archinstoo.default_profiles.desktops.nwg_shell import NwgShellProfile
from archinstoo.lib.installer import Installer
from archinstoo.lib.models.users import User
from archinstoo.lib.profile import profiles_handler
from archinstoo.lib.profile.base import GreeterType
from archinstoo.lib.profile.profiles_handler import ProfileHandler

if TYPE_CHECKING:
	from pathlib import Path

	import pytest


def _session(target: Path, monkeypatch: pytest.MonkeyPatch) -> Installer:
	session = Installer.__new__(Installer)
	session.target = target
	for name in ('add_additional_packages', 'enable_service', 'disable_service'):
		monkeypatch.setattr(session, name, lambda _: None, raising=False)
	return session


def test_installer_runs_per_user_without_reboot(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	# -w alone ends on `sudo systemctl reboot -f`; -s is what stops it
	calls: list[tuple[list[str], str | None]] = []
	session = _session(tmp_path, monkeypatch)

	def chroot(cmd: list[str], run_as: str | None = None) -> None:
		calls.append((cmd, run_as))

	monkeypatch.setattr(session, 'arch_chroot', chroot, raising=False)

	users = [User('ada', None, False), User('bob', None, False)]
	NwgShellProfile().provision(session, users)

	assert calls == [
		(['nwg-shell-installer', '-w', '-s'], 'ada'),
		(['nwg-shell-installer', '-w', '-s'], 'bob'),
	]


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
