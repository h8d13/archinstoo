from typing import TYPE_CHECKING

from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


# any special handling for a shell can go here bellow
# TODO: peak elitism busybox shell and remove bash
class ShellApp:
	def install(
		self,
		install_session: Installer,
		users: list[User],
	) -> None:
		# unique shells that need a package install; Shell.packages is empty for
		# the ones base already covers
		for shell in {user.shell for user in users}:
			if not (packages := shell.packages):
				continue

			debug(f'Installing shell: {shell.value}')
			install_session.add_additional_packages(packages)

		for user in users:
			shell_path = f'/usr/bin/{user.shell.value}'
			debug(f'Setting shell to {shell_path} for {user.username}')
			install_session.arch_chroot(['chsh', '-s', shell_path, user.username])
