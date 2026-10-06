# The temporary AUR build rules let grimoire's `pacman -S` for official repo
# deps keep the proxy env, and leave nothing behind once the build is done.

from types import SimpleNamespace
from typing import TYPE_CHECKING

from archinstoo.lib.models.authentication import AuthenticationConfiguration, PrivilegeEscalation
from archinstoo.lib.models.users import User
from archinstoo.lib.pm import aur

if TYPE_CHECKING:
	from pathlib import Path


def _build(tmp_path: Path, priv_esc: PrivilegeEscalation) -> dict[str, str]:
	(tmp_path / 'etc/sudoers.d').mkdir(parents=True)
	(tmp_path / 'usr/local/bin').mkdir(parents=True)
	(tmp_path / 'etc/doas.conf').write_text('permit persist :wheel\n')

	# snapshot the rules while grimoire would be running
	seen: dict[str, str] = {}

	def arch_chroot(_cmd: str, **_: object) -> None:
		for rule in ('etc/doas.conf', 'etc/sudoers.d/99-aur-build'):
			if (tmp_path / rule).exists():
				seen[rule] = (tmp_path / rule).read_text()

	installation = SimpleNamespace(target=tmp_path, add_additional_packages=lambda _: None, arch_chroot=arch_chroot)
	auth = AuthenticationConfiguration(users=[User('ada', None, True)], privilege_escalation=priv_esc)
	aur.run_grimoire_installation(['yay'], installation, auth)  # type: ignore[arg-type]
	return seen


def test_sudo_rule_keeps_proxy_env(tmp_path: Path) -> None:
	seen = _build(tmp_path, PrivilegeEscalation.Sudo)

	rule = seen['etc/sudoers.d/99-aur-build']
	assert 'Defaults:ada env_keep += "http_proxy https_proxy no_proxy' in rule
	assert 'ada ALL=(ALL) NOPASSWD: /usr/bin/pacman\n' in rule
	assert not (tmp_path / 'etc/sudoers.d/99-aur-build').exists()


def test_doas_rule_keeps_proxy_env(tmp_path: Path) -> None:
	seen = _build(tmp_path, PrivilegeEscalation.Doas)

	lines = seen['etc/doas.conf'].splitlines()
	for cmd in ('pacman', '/usr/bin/pacman'):
		assert f'permit nopass setenv {{ http_proxy https_proxy no_proxy HTTP_PROXY HTTPS_PROXY NO_PROXY }} ada as root cmd {cmd}' in lines
	# the user's own rules survive the cleanup, ours do not
	assert (tmp_path / 'etc/doas.conf').read_text() == 'permit persist :wheel\n'
