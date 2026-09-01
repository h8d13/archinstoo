from typing import TYPE_CHECKING

from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.application import TerminalConfiguration


class TerminalApp:
	def install(
		self,
		install_session: Installer,
		terminal_config: TerminalConfiguration,
	) -> None:
		# package and binary share a name for every entry in the enum
		terminal = terminal_config.terminal.value
		debug(f'Installing terminal: {terminal}')

		install_session.add_additional_packages([terminal])

		# profiles read this back through terminal_command(); the WMs whose
		# sensible-terminal helpers honour $TERMINAL (i3, labwc) need nothing else
		install_session.set_environment({'TERMINAL': terminal})
