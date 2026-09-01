# The log directory follows the human who invoked the command, never the cwd,
# the install layout or the effective uid. Under sudo the environment is root's
# (HOME=/root, XDG_STATE_HOME dropped by env_reset), so the invoker's path has
# to come from passwd for `./RUN` and `sudo ./RUN` to land in the same tree.

import pwd
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib import output

if TYPE_CHECKING:
	import pytest


def _unelevated(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.delenv('SUDO_USER', raising=False)
	monkeypatch.delenv('DOAS_USER', raising=False)


def _passwd_home(monkeypatch: pytest.MonkeyPatch, name: str, home: Path) -> None:
	def getpwnam(user: str) -> pwd.struct_passwd:
		if user != name:
			raise KeyError(user)
		return pwd.struct_passwd(('', '', 1000, 1000, '', str(home), ''))

	monkeypatch.setattr(pwd, 'getpwnam', getpwnam)


def test_sudo_logs_to_the_invoking_users_state_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# root's environment must not leak into the path
	monkeypatch.setenv('SUDO_USER', 'hadean')
	monkeypatch.setenv('HOME', '/root')
	monkeypatch.setenv('XDG_STATE_HOME', '/root/.local/state')
	_passwd_home(monkeypatch, 'hadean', tmp_path / 'home')

	assert output._default_log_dir() == tmp_path / 'home' / '.local' / 'state' / 'archinstoo'


def test_unelevated_honours_xdg_state_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	_unelevated(monkeypatch)
	monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))

	assert output._default_log_dir() == tmp_path / 'state' / 'archinstoo'


def test_real_root_logs_under_its_own_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# ISO, autologin, `su -`: no invoking human to hand the logs back to
	_unelevated(monkeypatch)
	monkeypatch.delenv('XDG_STATE_HOME', raising=False)
	monkeypatch.setenv('HOME', str(tmp_path / 'root'))

	assert output._default_log_dir() == tmp_path / 'root' / '.local' / 'state' / 'archinstoo'


def test_unknown_sudo_user_falls_back_instead_of_raising(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# SUDO_USER naming a user no longer in passwd must not take the logger down
	monkeypatch.setenv('SUDO_USER', 'ghost')
	monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
	_passwd_home(monkeypatch, 'someone-else', tmp_path / 'home')

	assert output._default_log_dir() == tmp_path / 'state' / 'archinstoo'


def test_log_dir_ignores_the_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	_unelevated(monkeypatch)
	monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))

	monkeypatch.chdir(tmp_path)
	from_here = output._default_log_dir()
	monkeypatch.chdir(Path(__file__).parent)

	assert output._default_log_dir() == from_here
