import shlex
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.chroot import KEEP_ENV
from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.models.authentication import PrivilegeEscalation
from archinstoo.lib.output import debug, info, warn

if TYPE_CHECKING:
	from collections.abc import Generator

	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.authentication import AuthenticationConfiguration

# what grimoire needs on the target before it can build anything from the AUR.
# base-devel spelled out (its member list minus sudo) so a doas install does
# not drag sudo in as a side effect of wanting a toolchain
AUR_BOOTSTRAP_PACKAGES = [
	'git',
	'archlinux-keyring',
	'autoconf',
	'automake',
	'binutils',
	'bison',
	'debugedit',
	'fakeroot',
	'file',
	'findutils',
	'flex',
	'gawk',
	'gcc',
	'gettext',
	'grep',
	'groff',
	'gzip',
	'libtool',
	'm4',
	'make',
	'pacman',
	'patch',
	'pkgconf',
	'sed',
	'texinfo',
	'which',
]


# grimoire elevates `pacman -S` for official repo deps: those downloads need
# the proxy too, and sudo/doas reset the env unless the rule keeps it
def sudo_aur_rule(username: str) -> str:
	return (
		f'Defaults:{username} env_keep += "{" ".join(KEEP_ENV)}"\n{username} '
		'ALL=(ALL) NOPASSWD: /usr/bin/pacman\n'
	)


def doas_aur_rules(username: str) -> str:
	# doas matches cmd against argv[0] as typed: grimoire runs `doas
	# pacman`, makepkg -i runs `doas /usr/bin/pacman` (PACMAN_PATH),
	# so both spellings need a rule
	keep = ' '.join(KEEP_ENV)
	return ''.join(
		f'permit nopass setenv {{ {keep} }} {username} as root cmd {cmd}\n'
		for cmd in ('pacman', '/usr/bin/pacman')
	)


# appended to the user's doas.conf, so cleanup strips only our lines
@contextmanager
def _doas_rule(target: Path, username: str) -> Generator[None]:
	conf = target / 'etc/doas.conf'
	rules = doas_aur_rules(username)
	debug(
		'Adding temporary doas rules for AUR build: permit nopass '
		f'{username} as root cmd pacman'
	)
	try:
		with conf.open('a') as doas:
			doas.write(rules)
		conf.chmod(0o644)
		yield
	finally:
		if conf.exists():
			debug(f'Removing temporary doas rule for {username}')
			added = set(rules.splitlines(keepends=True))
			lines = conf.read_text().splitlines(keepends=True)
			conf.write_text(
				''.join(line for line in lines if line not in added)
			)


@contextmanager
def _sudo_rule(target: Path, username: str) -> Generator[None]:
	rule = target / 'etc/sudoers.d/99-aur-build'
	try:
		rule.write_text(sudo_aur_rule(username))
		rule.chmod(0o440)
		yield
	finally:
		rule.unlink(missing_ok=True)


def run_grimoire_installation(
	packages: list[str],
	installation: Installer,
	auth_config: AuthenticationConfiguration | None = None,
) -> None:
	if not auth_config:
		warn('No auth config provided, skipping AUR packages')
		return

	build_user = next((u for u in auth_config.users if u.elev), None)

	if not build_user:
		warn('No elevated user found, skipping AUR packages')
		return

	installation.add_additional_packages(AUR_BOOTSTRAP_PACKAGES)

	grimoire_src = Path(__file__).parents[1] / 'grimoire.py'
	grimoire_dest = installation.target / 'usr/local/bin/grimoire'
	grimoire_src.copy(grimoire_dest, preserve_metadata=True)
	grimoire_dest.chmod(0o755)
	debug(f'Installed grimoire helper to {grimoire_dest}')

	temp_rule = (
		_doas_rule
		if auth_config.privilege_escalation == PrivilegeEscalation.Doas
		else _sudo_rule
	)

	with temp_rule(installation.target, build_user.username):
		for pkg in packages:
			info(f'Installing AUR package: {pkg}')
			try:
				installation.arch_chroot(
					'grimoire --no-color install --repo '
					f'AUR {shlex.quote(pkg)} --noconfirm',
					run_as=build_user.username,
					peek_output=True,
				)
			except SysCallError as e:
				warn(f'AUR package "{pkg}" failed: {e}')
