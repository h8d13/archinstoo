# The escalation package and its configuration go together: create_users
# straps sudo/doas only for an elevated user with a password, and a saved
# config never holds one. Rules for a tool that is not there help nobody.

from pathlib import Path
from types import SimpleNamespace

import pytest

from archinstoo.lib.authentication import accounts
from archinstoo.lib.models.authentication import PrivilegeEscalation
from archinstoo.lib.models.users import Password, User

_WRITTEN = ('etc/sudoers', 'etc/sudoers.d', 'etc/doas.conf')


def _create(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	password: Password | None,
	priv_esc: PrivilegeEscalation,
) -> tuple[list[str], list[str]]:
	(tmp_path / 'etc').mkdir()
	(tmp_path / 'etc/makepkg.conf').write_text('#PACMAN_AUTH=()\n')
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

	written = [name for name in _WRITTEN if (tmp_path / name).exists()]
	if (tmp_path / 'etc/makepkg.conf').read_text() != '#PACMAN_AUTH=()\n':
		written.append('etc/makepkg.conf')
	return strapped, written


@pytest.mark.parametrize('priv_esc', list(PrivilegeEscalation))
def test_passwordless_elevated_user_gets_no_escalation_setup(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	priv_esc: PrivilegeEscalation,
) -> None:
	# wheel stays (asserted in _create), su is on every system
	assert _create(tmp_path, monkeypatch, None, priv_esc) == ([], [])


@pytest.mark.parametrize(
	('priv_esc', 'written'),
	[
		(PrivilegeEscalation.Sudo, ['etc/sudoers', 'etc/sudoers.d']),
		(PrivilegeEscalation.Doas, ['etc/doas.conf', 'etc/makepkg.conf']),
		(PrivilegeEscalation.Run0, ['etc/makepkg.conf']),
	],
)
def test_elevated_user_with_a_password_gets_package_and_setup(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	priv_esc: PrivilegeEscalation,
	written: list[str],
) -> None:
	password = Password(enc_password='$y$hash')
	assert _create(tmp_path, monkeypatch, password, priv_esc) == (
		priv_esc.packages(),
		written,
	)
