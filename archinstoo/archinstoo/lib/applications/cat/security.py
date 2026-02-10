from typing import TYPE_CHECKING

from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class SecurityApp:
	@property
	def packages(self) -> list[str]:
		return [
			'apparmor',
		]

	@property
	def services(self) -> list[str]:
		return [
			'apparmor.service',
		]

	@property
	def kernel_params(self) -> list[str]:
		return [
			'lsm=landlock,lockdown,yama,integrity,apparmor,bpf',
		]

	def install(self, install_session: Installer) -> None:
		debug('Installing Security (AppArmor)')
		install_session.add_additional_packages(self.packages)
		install_session.enable_service(self.services)
		install_session.add_kernel_param(self.kernel_params)
