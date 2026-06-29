from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.models.application import Firewall, FirewallConfiguration
from archinstoo.lib.output import debug, warn

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class FirewallApp:
	@property
	def ufw_packages(self) -> list[str]:
		return [
			'ufw',
		]

	@property
	def fwd_packages(self) -> list[str]:
		return [
			'firewalld',
		]

	@property
	def ufw_services(self) -> list[str]:
		return [
			'ufw',
		]

	@property
	def fwd_services(self) -> list[str]:
		return [
			'firewalld',
		]

	def install(
		self,
		install_session: Installer,
		firewall_config: FirewallConfiguration,
	) -> None:
		debug(f'Installing firewall: {firewall_config.firewall.value}')

		match firewall_config.firewall:
			case Firewall.UFW:
				install_session.add_additional_packages(self.ufw_packages)
				install_session.enable_service(self.ufw_services)
				# write default conf file to enabled
				ufw_conf = install_session.target / 'etc/ufw/ufw.conf'
				ufw_conf.write_text(ufw_conf.read_text().replace('ENABLED=no', 'ENABLED=yes'))

			case Firewall.FWD:
				install_session.add_additional_packages(self.fwd_packages)
				install_session.enable_service(self.fwd_services)

	def allow_ssh(
		self,
		install_session: Installer,
		firewall: Firewall,
	) -> None:
		# openssh listens on 22 but a fresh firewalls blocks it
		# https://github.com/archlinux/archinstall/issues/4616
		# makes the ssh to the machione accesible on first boot.
		debug('Opening ssh ports in firewall')

		cmds = {
			Firewall.UFW: ['ufw', 'allow', 'ssh'],
			Firewall.FWD: ['firewall-offline-cmd', '--add-service=ssh'],
		}

		try:
			install_session.arch_chroot(cmds[firewall])
		except SysCallError as err:
			warn(f'Failed to open ssh in firewall: {err}')
