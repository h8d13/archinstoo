import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.models.authentication import PrivilegeEscalation
from archinstoo.lib.output import debug, info, warn

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.authentication import AuthenticationConfiguration

# what grimoire needs on the target before it can build anything from the AUR.
# base-devel spelled out (its member list minus sudo) so a doas install does
# not drag sudo in as a side effect of wanting a toolchain
__aur_bootstrap_packages__ = [
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

	installation.add_additional_packages(__aur_bootstrap_packages__)

	grimoire_src = Path(__file__).parents[1] / 'grimoire.py'
	grimoire_dest = installation.target / 'usr/local/bin/grimoire'
	grimoire_src.copy(grimoire_dest, preserve_metadata=True)
	grimoire_dest.chmod(0o755)
	debug(f'Installed grimoire helper to {grimoire_dest}')

	priv_esc = auth_config.privilege_escalation
	aur_rule = None

	try:
		if priv_esc == PrivilegeEscalation.Doas:
			doas_conf = installation.target / 'etc/doas.conf'
			aur_rule = doas_conf
			if not doas_conf.exists():
				doas_conf.write_text('')
			# doas matches cmd against argv[0] as typed: grimoire runs `doas
			# pacman`, makepkg -i runs `doas /usr/bin/pacman` (PACMAN_PATH),
			# so both spellings need a rule
			debug(f'Adding temporary doas rules for AUR build: permit nopass {build_user.username} as root cmd pacman')
			with doas_conf.open('a') as doas:
				for cmd in ('pacman', '/usr/bin/pacman'):
					doas.write(f'permit nopass {build_user.username} as root cmd {cmd}\n')
			doas_conf.chmod(0o644)
		else:
			sudoers_dir = installation.target / 'etc/sudoers.d'
			aur_rule = sudoers_dir / '99-aur-build'
			aur_rule.write_text(f'{build_user.username} ALL=(ALL) NOPASSWD: /usr/bin/pacman\n')
			aur_rule.chmod(0o440)

		for pkg in packages:
			info(f'Installing AUR package: {pkg}')
			try:
				installation.arch_chroot(
					f'grimoire --no-color install --repo AUR {shlex.quote(pkg)} --noconfirm',
					run_as=build_user.username,
					peek_output=True,
				)
			except SysCallError as e:
				warn(f'AUR package "{pkg}" failed: {e}')
	finally:
		if priv_esc == PrivilegeEscalation.Doas and aur_rule is not None and aur_rule.exists():
			debug(f'Removing temporary doas rule for {build_user.username}')
			with aur_rule.open('r') as f:
				lines = f.readlines()
			with aur_rule.open('w') as f:
				for line in lines:
					if f'permit nopass {build_user.username} as root' not in line:
						f.write(line)
		elif priv_esc != PrivilegeEscalation.Doas and aur_rule is not None:
			aur_rule.unlink(missing_ok=True)
