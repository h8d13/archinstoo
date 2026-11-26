# The escalation package and its configuration go together: create_users
# straps sudo/doas only for an elevated user with a password, and a saved
# config never holds one. Rules for a tool that is not there help nobody.

from pathlib import Path
from types import SimpleNamespace

import pytest

from archinstoo.lib.authentication import accounts
from archinstoo.lib.models.authentication import PrivilegeEscalation
from archinstoo.lib.models.users import Password, User

# makepkg.conf as pacman ships it
UNSET = {'etc/makepkg.conf': '#PACMAN_AUTH=()\n'}


def _create(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	password: Password | None,
	priv_esc: PrivilegeEscalation,
) -> tuple[list[str], dict[str, str]]:
	(tmp_path / 'etc').mkdir()
	(tmp_path / 'etc/makepkg.conf').write_text(UNSET['etc/makepkg.conf'])
	monkeypatch.setattr(accounts, 'run', lambda *_, **__: None)
	# sudoers.d is 0440: fine for root, not traversable for whoever runs pytest
	monkeypatch.setattr(Path, 'chmod', lambda *_, **__: None)

	strapped: list[str] = []
	commands: list[list[str]] = []
	installation = SimpleNamespace(
		target=tmp_path,
		pacman=SimpleNamespace(strap=strapped.extend),
		arch_chroot=commands.append,
	)
	accounts.create_users(
		installation,  # type: ignore[arg-type]
		User('ada', password, True),
		priv_esc,
	)
	assert commands == [['useradd', '-m', '-G', 'wheel', 'ada']]

	# every file under the target's etc, with what it holds
	written = {
		str(path.relative_to(tmp_path)): path.read_text()
		for path in (tmp_path / 'etc').rglob('*')
		if path.is_file()
	}
	return strapped, written


@pytest.mark.parametrize('priv_esc', list(PrivilegeEscalation))
def test_passwordless_elevated_user_gets_no_escalation_setup(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	priv_esc: PrivilegeEscalation,
) -> None:
	# wheel stays (asserted in _create), su is on every system
	warnings: list[str] = []
	monkeypatch.setattr(accounts, 'warn', warnings.append)
	assert _create(tmp_path, monkeypatch, None, priv_esc) == ([], UNSET)
	# the config named a tool: not setting it up is said
	assert warnings == [
		f'No elevated user has a password: {priv_esc.value} is not set up'
	]


@pytest.mark.parametrize(
	('priv_esc', 'written'),
	[
		(
			PrivilegeEscalation.Sudo,
			{
				# stubbed strap: no sudoers.d, the include is added
				'etc/sudoers': '@includedir /etc/sudoers.d\n',
				'etc/sudoers.d/00_ada': 'ada ALL=(ALL) ALL\n',
				**UNSET,
			},
		),
		(
			PrivilegeEscalation.Doas,
			{
				'etc/doas.conf': 'permit ada as root\n',
				'etc/makepkg.conf': 'PACMAN_AUTH=(doas)\n',
			},
		),
		(
			PrivilegeEscalation.Run0,
			{'etc/makepkg.conf': 'PACMAN_AUTH=(run0)\n'},
		),
	],
)
def test_elevated_user_with_a_password_gets_package_and_setup(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	priv_esc: PrivilegeEscalation,
	written: dict[str, str],
) -> None:
	password = Password(enc_password='$y$hash')
	assert _create(tmp_path, monkeypatch, password, priv_esc) == (
		priv_esc.packages(),
		written,
	)
