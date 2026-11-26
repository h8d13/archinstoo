from typing import TYPE_CHECKING

from archinstoo.lib.models.applications import Security, SecurityConfiguration
from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer

# every tool is its own package; these are what some need on top
_SERVICES = {
	Security.APPARMOR: 'apparmor',
	Security.FAIL2BAN: 'fail2ban',
	Security.AUDIT: 'auditd',
}
_KERNEL_PARAMS = {
	Security.APPARMOR: ['lsm=landlock,lockdown,yama,integrity,apparmor,bpf'],
}


class SecurityApp:
	def install(
		self,
		install_session: Installer,
		security_config: SecurityConfiguration,
	) -> None:
		for tool in security_config.tools:
			debug(f'Installing security: {tool.value}')
			install_session.add_additional_packages([tool.value])

			if service := _SERVICES.get(tool):
				install_session.enable_service(service)
			if params := _KERNEL_PARAMS.get(tool):
				install_session.add_kernel_param(params)
