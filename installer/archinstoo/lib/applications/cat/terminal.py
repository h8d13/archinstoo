from typing import TYPE_CHECKING

from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.applications import TerminalConfiguration


class TerminalApp:
	def install(
		self,
		install_session: Installer,
		terminal_config: TerminalConfiguration,
	) -> None:
		terminal = terminal_config.terminal
		debug(f'Installing terminal: {terminal.value}')

		install_session.add_additional_packages(terminal.packages)

		# this is all a profile gets: shipped WM configs keep whatever terminal
		# upstream hardcodes, only our own (noctalia) launch $TERMINAL
		install_session.set_environment({'TERMINAL': terminal.value})
