import shlex
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Final

from archinstoo.lib.authentication.accounts import (
	DOAS_CONF,
	PACMAN_AUTH_UNSET,
	SUDOERS_DIR,
)
from archinstoo.lib.chroot import KEEP_ENV
from archinstoo.lib.command import run
from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.models.authentication import PrivilegeEscalation
from archinstoo.lib.models.packages import AUR_BOOTSTRAP_PACKAGES
from archinstoo.lib.output import debug, info, warn

if TYPE_CHECKING:
	from collections.abc import Generator

	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.authentication import AuthenticationConfiguration


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
	conf = target / DOAS_CONF.relative_to_root()
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
	rule = target / SUDOERS_DIR.relative_to_root() / '99-aur-build'
	try:
		rule.write_text(sudo_aur_rule(username))
		rule.chmod(0o440)
		yield
	finally:
		rule.unlink(missing_ok=True)


# neither sudo nor doas on the target: su is in base, and makepkg and grimoire
# both fall back to it, but it asks for root's password. For the build wheel
# is trusted (the line util-linux ships commented out) and makepkg.conf names
# su, which keeps grimoire off run0 where polkit happens to be installed
SU_PAM_RULE: Final = 'auth sufficient pam_wheel.so trust use_uid\n'
SU_PACMAN_AUTH: Final = "PACMAN_AUTH=(su root -c '%c')"


# an edited copy mounted over a file of the target. The file itself is never
# written: it is as it was whatever ends the build, and a killed install
# leaves a mount behind, not a rule on the installed system
@contextmanager
def _mounted_over(path: Path, text: str) -> Generator[None]:
	with tempfile.NamedTemporaryFile('w', prefix='archinstoo-aur-') as copy:
		copy.write(text)
		copy.flush()
		shutil.copymode(path, copy.name)
		run(['mount', '--bind', copy.name, str(path)])
		try:
			yield
		finally:
			run(['umount', str(path)])


@contextmanager
def _su_rule(target: Path, username: str) -> Generator[None]:
	pam = target / 'etc/pam.d/su'
	if not pam.exists():
		# a target that keeps /etc for machine state (Caeoma) has the file
		# under /usr/lib, where PAM looks next
		pam = target / 'usr/lib/pam.d/su'

	makepkg_conf = target / 'etc/makepkg.conf'
	shipped = makepkg_conf.read_text()
	if PACMAN_AUTH_UNSET not in shipped:
		warn(f'{makepkg_conf} sets PACMAN_AUTH itself, su is not named in it')

	debug(f'Trusting wheel for su while {username} builds from the AUR')
	with (
		_mounted_over(pam, SU_PAM_RULE + pam.read_text()),
		_mounted_over(
			makepkg_conf, shipped.replace(PACMAN_AUTH_UNSET, SU_PACMAN_AUTH)
		),
	):
		yield


# what lets the build user run pacman unasked while grimoire builds. run0 has
# no entry: it needs a booted system
_TEMP_RULES: Final = {
	PrivilegeEscalation.Sudo: _sudo_rule,
	PrivilegeEscalation.Doas: _doas_rule,
	None: _su_rule,
}


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

	# the rule goes with what create_users set up: su as well where sudo or
	# doas are named but no elevated user has a password for them
	temp_rule = _TEMP_RULES.get(auth_config.effective_escalation)
	if not temp_rule:
		warn('AUR packages cannot build under run0, skipping them')
		return

	installation.add_additional_packages(AUR_BOOTSTRAP_PACKAGES)

	grimoire_src = Path(__file__).parents[1] / 'grimoire.py'
	grimoire_dest = installation.target / 'usr/local/bin/grimoire'
	grimoire_src.copy(grimoire_dest, preserve_metadata=True)
	grimoire_dest.chmod(0o755)
	debug(f'Installed grimoire helper to {grimoire_dest}')

	try:
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
	except (OSError, SysCallError) as e:
		# these packages are extras: a rule that cannot be set up, or taken
		# back, is no reason to stop before fstab is written
		warn(f'AUR build rule failed, packages may be missing: {e}')
