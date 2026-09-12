import re
from subprocess import CalledProcessError
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.general import run
from archinstoo.lib.models.authentication import PrivilegeEscalation
from archinstoo.lib.models.users import User
from archinstoo.lib.output import debug, error, info, warn

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer

# cloning a user stash
__stash_packages__ = ['git']


def _enable_sudo(installation: Installer, user: User, group: bool = False) -> None:
	info(f'Enabling sudo permissions for {user.username}')

	sudoers_dir = installation.target / 'etc/sudoers.d'

	# Creates directory if not exists
	if not sudoers_dir.exists():
		sudoers_dir.mkdir(parents=True)
		# Guarantees sudoer confs directory recommended perms
		sudoers_dir.chmod(0o440)
		# Appends a reference to the sudoers file, because if we are here sudoers.d did not exist yet
		with (installation.target / 'etc/sudoers').open('a') as sudoers:
			sudoers.write('@includedir /etc/sudoers.d\n')

	# We count how many files are there already so we know which number to prefix the file with
	num_of_rules_already = len(list(sudoers_dir.iterdir()))
	file_num_str = f'{num_of_rules_already:02d}'  # We want 00_user1, 01_user2, etc

	# Guarantees that username str does not contain invalid characters for a linux file name:
	# \ / : * ? " < > |
	safe_username_file_name = re.sub(r'(\\|\/|:|\*|\?|"|<|>|\|)', '', user.username)

	rule_file = sudoers_dir / f'{file_num_str}_{safe_username_file_name}'

	with rule_file.open('a') as sudoers:
		sudoers.write(f'{"%" if group else ""}{user.username} ALL=(ALL) ALL\n')

	# Guarantees sudoer conf file recommended perms
	rule_file.chmod(0o440)


# under seatd, compositors need seat membership to reach /run/seatd.sock (DRM/input).
# group exists only when the seatd package landed (sysusers); skip otherwise so
# usermod can't abort the install on logind/polkit systems.
def add_to_seat_group(installation: Installer, usernames: list[str]) -> None:
	group_lines = installation.target.joinpath('etc/group').read_text().splitlines()
	if not any(line.startswith('seat:') for line in group_lines):
		debug('No seat group on target (seatd not installed), skipping seat membership')
		return
	for name in usernames:
		debug(f'Adding {name} to seat group')
		installation.arch_chroot(['usermod', '-a', '-G', 'seat', name])


def _enable_doas(installation: Installer, user: User) -> None:
	info(f'Enabling doas permissions for {user.username}')

	doas_conf = installation.target / 'etc/doas.conf'

	with doas_conf.open('a') as doas:
		doas.write(f'permit {user.username} as root\n')

	# doas.conf must be owned by root and not writable by others
	doas_conf.chmod(0o644)


def create_users(
	installation: Installer,
	users: User | list[User],
	privilege_escalation: PrivilegeEscalation | None = PrivilegeEscalation.Sudo,
) -> None:
	if not isinstance(users, list):
		users = [users]

	info(f'Creating {len(users)} user account(s): {", ".join(u.username for u in users)}', step=True)

	# Install the privilege escalation package
	if privilege_escalation is not None and User.any_elevated(users):
		installation.pacman.strap(privilege_escalation.packages())

	_configure_makepkg(installation, privilege_escalation)

	for user in users:
		_create_user(installation, user, privilege_escalation)


def _configure_makepkg(installation: Installer, privilege_escalation: PrivilegeEscalation | None) -> None:
	# makepkg tries sudo then su by default, only doas/run0 need an override
	if privilege_escalation is None:
		return

	auth_binary = {
		PrivilegeEscalation.Doas: 'doas',
		PrivilegeEscalation.Run0: 'run0',
	}.get(privilege_escalation)

	if auth_binary is None:
		debug(f'{privilege_escalation.value} uses makepkg default PACMAN_AUTH, nothing to set')
		return

	makepkg_conf = installation.target / 'etc/makepkg.conf'
	if not makepkg_conf.exists():
		warn(f'{makepkg_conf} missing, PACMAN_AUTH not set for {auth_binary}')
		return

	content = makepkg_conf.read_text()
	content = content.replace('#PACMAN_AUTH=()', f'PACMAN_AUTH=({auth_binary})')
	makepkg_conf.write_text(content)
	debug(f'Set PACMAN_AUTH=({auth_binary}) in makepkg.conf')


def _create_user(
	installation: Installer,
	user: User,
	privilege_escalation: PrivilegeEscalation | None = PrivilegeEscalation.Sudo,
) -> None:
	info(f'Creating user {user.username}')

	cmd = ['useradd', '-m']

	if user.elev:
		cmd += ['-G', 'wheel']

	cmd.append(user.username)

	try:
		installation.arch_chroot(cmd)
	except CalledProcessError:
		# user may already exist (e.g. installing onto running system)
		info(f'User {user.username} already exists, skipping creation')

	set_user_password(installation, user)

	for group in user.groups:
		debug(f'Adding {user.username} to group {group}')
		installation.arch_chroot(['gpasswd', '-a', user.username, group])

	if user.elev:
		match privilege_escalation:
			case PrivilegeEscalation.Sudo:
				_enable_sudo(installation, user)
			case PrivilegeEscalation.Doas:
				_enable_doas(installation, user)
			case PrivilegeEscalation.Run0 | None:
				pass  # run0/su via wheel group - no extra config needed

	for stash_url in user.stash_urls:
		_clone_user_stash(installation, user.username, stash_url)


def _clone_user_stash(installation: Installer, username: str, stash_url: str) -> None:
	info(f'Cloning {stash_url} for {username}')

	installation.add_additional_packages(__stash_packages__)

	url, _, branch = stash_url.partition('#')
	repo_name = url.rstrip('/').split('/')[-1].removesuffix('.git')
	stash_dir = f'/home/{username}/.stash'
	clone_cmd = ['git', 'clone', '--depth', '1']
	if branch:
		clone_cmd += ['-b', branch]
	clone_cmd += [url, f'{stash_dir}/{repo_name}']

	try:
		installation.arch_chroot(['mkdir', '-p', stash_dir])
		installation.arch_chroot(clone_cmd)
		installation.chown_tree(username, stash_dir)
	except CalledProcessError as err:
		error(f'Failed to clone stash for {username}: {err}')


def set_user_password(installation: Installer, user: User) -> bool:
	info(f'Setting password for {user.username}')

	if not user.password:
		debug('User password not set')
		return False

	enc_password = user.password.enc_password

	if not enc_password:
		debug('User password is empty')
		return False

	input_data = f'{user.username}:{enc_password}'.encode()
	cmd = [*installation.arch_chroot_prefix, 'chpasswd', '--encrypted']

	try:
		run(cmd, input_data=input_data)
		return True
	except CalledProcessError as err:
		debug(f'Error setting user password: {err}')
		return False


def lock_root_account(installation: Installer) -> bool:
	info('Locking root account')

	try:
		installation.arch_chroot('passwd -l root')
		return True
	except SysCallError as err:
		error(f'Failed to lock root account: {err}')
		return False
