from subprocess import CalledProcessError
from typing import TYPE_CHECKING

from archinstoo.lib.output import error, info

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer

# a user's dotfiles repo, cloned into ~/.stash right after useradd
# cloning a user stash
__stash_packages__ = ['git']


def clone_user_stash(installation: Installer, username: str, stash_url: str) -> None:
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
