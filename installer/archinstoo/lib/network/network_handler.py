from typing import TYPE_CHECKING

from archinstoo.lib.output import warn
from archinstoo.lib.utils.env import Os

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.network import DnsConfiguration, NetworkConfiguration
	from archinstoo.lib.models.profile import ProfileConfiguration


class NetworkHandler:
	def install_network_config(
		self,
		network_config: NetworkConfiguration,
		installation: Installer,
		profile_config: ProfileConfiguration | None = None,
	) -> None:
		from archinstoo.lib.models.network import NM_DESKTOP_EXTRA, NicType

		match network_config.type:
			case NicType.ISO:
				installation.copy_iso_network_config(
					enable_services=True,
				)
			case NicType.NM | NicType.NM_IWD:
				installation.add_additional_packages(network_config.type.packages)

				if profile_config and profile_config.profiles and profile_config.has_desktop_profile():
					installation.add_additional_packages(NM_DESKTOP_EXTRA)

				installation.enable_service('NetworkManager')

				if network_config.type == NicType.NM_IWD:
					_configure_nm_iwd(installation)
					installation.disable_service('iwd')

				# NM picks dns=systemd-resolved by itself once /etc/resolv.conf is
				# the resolved stub (NetworkManager.conf, [main] dns), which puts
				# every network type behind the same resolver
				installation.enable_service('systemd-resolved')
				installation.link_resolved_stub()

			case NicType.IWD:
				installation.add_additional_packages(network_config.type.packages)
				_configure_iwd_standalone(installation)
				installation.enable_service('iwd')
				installation.enable_service('systemd-networkd')
				installation.enable_service('systemd-resolved')

			case NicType.MANUAL:
				for nic in network_config.nics:
					installation.configure_nic(nic)
				installation.enable_service('systemd-networkd')
				installation.enable_service('systemd-resolved')

		if network_config.dns:
			_configure_dns(installation, network_config.dns)


def _configure_dns(installation: Installer, dns: DnsConfiguration) -> None:
	# resolved takes the drop-in whatever brought it up; on a foreign host
	# link_resolved_stub() copied a resolv.conf instead of the stub symlink, so
	# NetworkManager stays in its default mode and writes past it
	if Os.running_from_foreign():
		warn('NetworkManager will not use the DNS choice: /etc/resolv.conf is not the resolved stub')

	conf_dir = installation.target / 'etc/systemd/resolved.conf.d'
	conf_dir.mkdir(parents=True, exist_ok=True)
	(conf_dir / 'dns.conf').write_text(dns.as_resolved_config())


def _configure_nm_iwd(installation: Installer) -> None:
	nm_conf_dir = installation.target / 'etc/NetworkManager/conf.d'
	nm_conf_dir.mkdir(parents=True, exist_ok=True)
	(nm_conf_dir / 'wifi_backend.conf').write_text('[device]\nwifi.backend=iwd\n')


def _configure_iwd_standalone(installation: Installer) -> None:
	# iwd manages wireless only; systemd-networkd handles wired DHCP.
	iwd_conf_dir = installation.target / 'etc/iwd'
	iwd_conf_dir.mkdir(parents=True, exist_ok=True)
	(iwd_conf_dir / 'main.conf').write_text('[General]\nEnableNetworkConfiguration=true\n\n[Network]\nNameResolvingService=systemd\n')

	networkd_dir = installation.target / 'etc/systemd/network'
	networkd_dir.mkdir(parents=True, exist_ok=True)
	(networkd_dir / '20-wired.network').write_text('[Match]\nType=ether\nKind=!*\n\n[Network]\nDHCP=yes\n')

	installation.link_resolved_stub()
