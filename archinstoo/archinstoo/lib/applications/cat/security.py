from typing import TYPE_CHECKING

from archinstoo.lib.models.application import Security, SecurityConfiguration
from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class SecurityApp:
	@property
	def apparmor_packages(self) -> list[str]:
		return [
			'apparmor',
		]

	@property
	def apparmor_services(self) -> list[str]:
		return [
			'apparmor.service',
		]

	@property
	def apparmor_kernel_params(self) -> list[str]:
		return [
			'lsm=landlock,lockdown,yama,integrity,apparmor,bpf',
		]

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
				case Security.APPARMOR:
					debug('Installing Security (AppArmor)')
					install_session.add_additional_packages(self.apparmor_packages)
					install_session.enable_service(self.apparmor_services)
					install_session.add_kernel_param(self.apparmor_kernel_params)

				case Security.FIREJAIL:
					debug('Installing Security (Firejail)')
					install_session.add_additional_packages(self.firejail_packages)

				case Security.BUBBLEWRAP:
					debug('Installing Security (Bubblewrap)')
					install_session.add_additional_packages(self.bubblewrap_packages)
