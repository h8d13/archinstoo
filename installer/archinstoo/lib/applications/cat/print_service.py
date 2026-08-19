from typing import TYPE_CHECKING

from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class PrintServiceApp:
	@property
	def packages(self) -> list[str]:
		return ['cups', 'system-config-printer', 'cups-pk-helper', 'ghostscript']
		# PostScript interp https://github.com/archlinux/archinstall/issues/4595

	@property
	def services(self) -> list[str]:
		return [
			'cups',
			# cups dnssd backend needs the daemon running to discover network
			# printers (temporary queues cover IPP Everywhere in DE dialogs).
			# not covered: .local via glibc (nss-mdns + nsswitch edit) and
			# pre-IPP printers needing vendor drivers (hplip etc.)
			'avahi-daemon',
		]

	def install(self, install_session: Installer) -> None:
		debug('Installing print service')
		install_session.add_additional_packages(self.packages)
		install_session.enable_service(self.services)
