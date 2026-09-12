from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.linux_path import LPath
from archinstoo.lib.models.network import ISO_PSK_EXTRA, NM_DESKTOP_EXTRA, MacAddressPolicy, NicType
from archinstoo.lib.output import debug, info, warn
from archinstoo.lib.utils.env import Os

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.network import DnsConfiguration, NetworkConfiguration, Nic
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
				_copy_iso_network_config(installation, enable_services=True)
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
					_configure_nic(installation, nic)
				installation.enable_service('systemd-networkd')

		_use_resolved(installation)

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


def _copy_iso_network_config(installation: Installer, enable_services: bool = False) -> None:
	# Live mode targets the running system: configs already in place,
	# copying a path onto itself raises OSError (Errno 22). Skip the
	# copies, keep service enablement.
	on_host = installation.target == Path('/')

	# Copy (if any) iwd password and config files
	iwd_dir = LPath('/var/lib/iwd')
	if psk_files := list(iwd_dir.glob('*.psk')):
		info(f'Copying {len(psk_files)} iwd profile(s) to target')
		if not on_host:
			iwd_target = installation.target / iwd_dir.relative_to_root()
			iwd_target.mkdir(parents=True, exist_ok=True)

			for psk in psk_files:
				psk.copy(iwd_target / psk.name, preserve_metadata=True)

		if enable_services:
			# every script runs this after minimal_installation, the target takes packages
			installation.add_additional_packages(ISO_PSK_EXTRA)
			installation.enable_service('iwd')

	# Copy (if any) systemd-networkd config files
	network_dir = LPath('/etc/systemd/network')
	if netconfigurations := list(network_dir.glob('*')):
		info(f'Copying {len(netconfigurations)} systemd-networkd config(s) to target')
		if not on_host:
			network_target = installation.target / network_dir.relative_to_root()
			network_target.mkdir(parents=True, exist_ok=True)

			for netconf_file in netconfigurations:
				netconf_file.copy(network_target / netconf_file.name, preserve_metadata=True)

		if enable_services:
			installation.enable_service('systemd-networkd')

	if not psk_files and not netconfigurations:
		debug('No iwd profiles or systemd-networkd configs found on ISO')


def _configure_nic(installation: Installer, nic: Nic) -> None:
	conf = nic.as_systemd_config()

	with (installation.target / f'etc/systemd/network/10-{nic.iface}.network').open('a') as netconf:
		netconf.write(str(conf))
	info(f'Wrote network config for {nic.iface}')


def _use_resolved(installation: Installer) -> None:
	# every network type; the stub symlink is what switches NetworkManager
	# to dns=systemd-resolved https://wiki.archlinux.org/title/Systemd-resolved#DNS
	installation.enable_service('systemd-resolved')

	resolv = installation.target / 'etc/resolv.conf'
	resolv.unlink(missing_ok=True)

	# the stub only resolves once systemd-resolved runs on the target. From a
	# foreign (non-systemd) host that flow isn't guaranteed, so copy the
	# host's working resolv.conf content instead of a dangling symlink.
	if Os.running_from_foreign():
		host_resolv = Path('/etc/resolv.conf')
		if host_resolv.is_file():  # follows symlink, False if dangling
			resolv.write_text(host_resolv.read_text())
			debug(f'Copied host {host_resolv} to target (foreign host)')
		else:
			debug('No host /etc/resolv.conf to copy, leaving target unset')
		return

	resolv.symlink_to('/run/systemd/resolve/stub-resolv.conf')
	debug(f'Linked {resolv} to systemd-resolved stub')
