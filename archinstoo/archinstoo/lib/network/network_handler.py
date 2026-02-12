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
				if network_config.type == NicType.NM:
					packages.append('wpa_supplicant')

				installation.add_additional_packages(packages)

				if profile_config and profile_config.profiles and profile_config.has_desktop_profile():
					installation.add_additional_packages('network-manager-applet')

				installation.enable_service('NetworkManager.service')
				if network_config.type == NicType.NM_IWD:
					packages.append('iwd')
					installation.configure_nm_iwd()
					installation.disable_service('iwd.service')

			case NicType.MANUAL:
				for nic in network_config.nics:
					installation.configure_nic(nic)
				installation.enable_service('systemd-networkd')
				installation.enable_service('systemd-resolved')
