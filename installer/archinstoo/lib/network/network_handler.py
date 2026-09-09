from typing import TYPE_CHECKING

from archinstoo.lib.models.network import NM_DESKTOP_EXTRA, MacAddressPolicy, NicType
from archinstoo.lib.output import debug, info, warn
from archinstoo.lib.utils.env import Os

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.network import DnsConfiguration, NetworkConfiguration
	from archinstoo.lib.profile.config import ProfileConfiguration


class NetworkHandler:
	def install_network_config(
		self,
		network_config: NetworkConfiguration,
		installation: Installer,
		profile_config: ProfileConfiguration | None = None,
	) -> None:
		info('Writing network configuration...')
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

			case NicType.IWD:
				installation.add_additional_packages(network_config.type.packages)
				_configure_iwd_standalone(installation, network_config.mac_address)
				installation.enable_service('iwd')
				installation.enable_service('systemd-networkd')

			case NicType.MANUAL:
				for nic in network_config.nics:
					installation.configure_nic(nic)
				installation.enable_service('systemd-networkd')

		installation.use_resolved()

		if network_config.dns:
			_configure_dns(installation, network_config.dns)

		if network_config.mac_address is not MacAddressPolicy.KEEP:
			_configure_mac_address(installation, network_config.type, network_config.mac_address)


def _configure_dns(installation: Installer, dns: DnsConfiguration) -> None:
	# on a foreign host use_resolved() left a copied resolv.conf, not the stub,
	# so NetworkManager stays in default mode and writes past resolved
	if Os.running_from_foreign():
		warn('NetworkManager will not use the DNS choice: /etc/resolv.conf is not the resolved stub')

	conf_dir = installation.target / 'etc/systemd/resolved.conf.d'
	conf_dir.mkdir(parents=True, exist_ok=True)
	(conf_dir / 'dns.conf').write_text(dns.as_resolved_config())
	debug(f'Wrote {conf_dir / "dns.conf"}')


def _configure_nm_iwd(installation: Installer) -> None:
	nm_conf_dir = installation.target / 'etc/NetworkManager/conf.d'
	nm_conf_dir.mkdir(parents=True, exist_ok=True)
	(nm_conf_dir / 'wifi_backend.conf').write_text('[device]\nwifi.backend=iwd\n')
	debug(f'Wrote {nm_conf_dir / "wifi_backend.conf"}')


def _configure_iwd_standalone(installation: Installer, mac: MacAddressPolicy) -> None:
	# iwd manages wireless only; systemd-networkd handles wired DHCP.
	general = 'EnableNetworkConfiguration=true\n'
	if mac is not MacAddressPolicy.KEEP:
		general += mac.as_iwd_config()

	iwd_conf_dir = installation.target / 'etc/iwd'
	iwd_conf_dir.mkdir(parents=True, exist_ok=True)
	(iwd_conf_dir / 'main.conf').write_text(f'[General]\n{general}\n[Network]\nNameResolvingService=systemd\n')
	debug(f'Wrote {iwd_conf_dir / "main.conf"}')

	networkd_dir = installation.target / 'etc/systemd/network'
	networkd_dir.mkdir(parents=True, exist_ok=True)
	(networkd_dir / '20-wired.network').write_text('[Match]\nType=ether\nKind=!*\n\n[Network]\nDHCP=yes\n')
	debug(f'Wrote {networkd_dir / "20-wired.network"}')


def _configure_mac_address(installation: Installer, nic_type: NicType, mac: MacAddressPolicy) -> None:
	# NetworkManager owns the address on its paths; elsewhere udev's .link
	# does wired and iwd's main.conf did wireless
	if nic_type in (NicType.NM, NicType.NM_IWD):
		nm_conf_dir = installation.target / 'etc/NetworkManager/conf.d'
		nm_conf_dir.mkdir(parents=True, exist_ok=True)
		(nm_conf_dir / 'mac_address.conf').write_text(mac.as_nm_config())
		debug(f'Wrote {nm_conf_dir / "mac_address.conf"}')

		if nic_type is NicType.NM_IWD:
			# NM's iwd device never applies cloned-mac-address (no
			# hw_addr_set_cloned in nm-device-iwd.c), so wireless takes
			# iwd's own knob; the NM drop-in still covers ethernet
			iwd_conf_dir = installation.target / 'etc/iwd'
			iwd_conf_dir.mkdir(parents=True, exist_ok=True)
			(iwd_conf_dir / 'main.conf').write_text(f'[General]\n{mac.as_iwd_config()}')
			debug(f'Wrote {iwd_conf_dir / "main.conf"}')
		return

	if mac is MacAddressPolicy.STABLE:
		warn('stable MAC addresses need NetworkManager; wired links keep their hardware address')
		return

	link_dir = installation.target / 'etc/systemd/network'
	link_dir.mkdir(parents=True, exist_ok=True)
	(link_dir / '00-mac-address.link').write_text(mac.as_link_config())
	debug(f'Wrote {link_dir / "00-mac-address.link"}')
