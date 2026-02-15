from typing import TYPE_CHECKING

from archinstoo.lib.models.users import Shell, User
from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class ShellApp:
	def install(
		self,
		install_session: Installer,
		users: list[User],
	) -> None:
		# collect unique shells that need a package install
		# bash and rbash are already available (rbash is bash in restricted mode)
		shells_needed = {user.shell for user in users if user.shell not in (Shell.BASH, Shell.RBASH)}

		for shell in shells_needed:
			debug(f'Installing shell: {shell.value}')
			install_session.add_additional_packages([shell.value])

		for user in users:
			shell_path = f'/usr/bin/{user.shell.value}'
			debug(f'Setting shell to {shell_path} for {user.username}')
			install_session.arch_chroot(f'chsh -s {shell_path} {user.username}')
