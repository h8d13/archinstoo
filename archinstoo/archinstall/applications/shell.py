from __future__ import annotations

from typing import TYPE_CHECKING

from archinstall.lib.models.application import Shell, ShellConfiguration
from archinstall.lib.models.users import User
from archinstall.lib.output import debug

if TYPE_CHECKING:
	from archinstall.lib.installer import Installer


class ShellApp:
	def install(
		self,
		install_session: Installer,
		shell_config: ShellConfiguration,
		users: list[User] | None = None,
	) -> None:
		shell = shell_config.shell
		debug(f'Installing shell: {shell.value}')

		# bash is already installed, only install if different
		if shell != Shell.BASH:
			install_session.add_additional_packages([shell.value])

		if users is None:
			return

		shell_path = f'/usr/bin/{shell.value}'
		for user in users:
			debug(f'Setting shell to {shell_path} for {user.username}')
			install_session.arch_chroot(f'chsh -s {shell_path} {user.username}')
