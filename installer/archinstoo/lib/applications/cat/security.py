from typing import TYPE_CHECKING

from archinstoo.lib.models.applications import Security, SecurityConfiguration
from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class SecurityApp:
	@property
	def firejail_packages(self) -> list[str]:
		return [
			'firejail',
		]

	@property
	def bubblewrap_packages(self) -> list[str]:
		return [
			'bubblewrap',
		]

	def install(
		self,
		install_session: Installer,
		security_config: SecurityConfiguration,
	) -> None:
		for tool in security_config.tools:
			match tool:
				case Security.FIREJAIL:
					debug('Installing security: Firejail')
					install_session.add_additional_packages(self.firejail_packages)

				case Security.BUBBLEWRAP:
					debug('Installing security: Bubblewrap')
					install_session.add_additional_packages(self.bubblewrap_packages)

				case Security.FAIL2BAN:
					debug('Installing security: Fail2ban')
					install_session.add_additional_packages([tool.value])
					install_session.enable_service('fail2ban')

				case Security.PAM_U2F:
					debug('Installing security: pam-u2f')
					install_session.add_additional_packages(['pam-u2f'])

				case Security.AUDIT:
					debug('Installing security: audit')
					install_session.add_additional_packages(['audit'])
					install_session.enable_service('auditd')
