from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.network import NetworkConfiguration
	from archinstoo.lib.models.profile import ProfileConfiguration


class NetworkHandler:
	def install_network_config(
		self,
		network_config: NetworkConfiguration,
		installation: Installer,
		profile_config: ProfileConfiguration | None = None,
	) -> None:
		from archinstoo.lib.models.network import NicType

		match network_config.type:
			case NicType.ISO:
				installation.copy_iso_network_config(
					enable_services=True,
				)
			case NicType.NM | NicType.NM_IWD:
				packages = ['networkmanager']
				if network_config.type == NicType.NM:  # legacy
					packages.append('wpa_supplicant')
				else:  # iwd for intel devices
					packages.append('iwd')

				installation.add_additional_packages(packages)

				if profile_config and profile_config.profiles and profile_config.has_desktop_profile():
					installation.add_additional_packages('network-manager-applet')

				installation.enable_service('NetworkManager')

				if network_config.type == NicType.NM_IWD:
					_configure_nm_iwd(installation)
					installation.disable_service('iwd')

			case NicType.IWD:
				installation.add_additional_packages(['iwd'])
				_configure_iwd_standalone(installation)
				installation.enable_service('iwd')
				installation.enable_service('systemd-networkd')
				installation.enable_service('systemd-resolved')

			case NicType.MANUAL:
				for nic in network_config.nics:
					installation.configure_nic(nic)
				installation.enable_service('systemd-networkd')
				installation.enable_service('systemd-resolved')


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
