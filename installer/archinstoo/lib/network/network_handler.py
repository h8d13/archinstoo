import textwrap
from typing import TYPE_CHECKING

from archinstoo.lib.linux_path import LPath
from archinstoo.lib.models.network import ISO_PSK_EXTRA, NM_DESKTOP_EXTRA, NicType
from archinstoo.lib.output import debug, info, warn

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.network import DnsConfiguration, NetworkConfiguration, Nic
	from archinstoo.lib.profile.config import ProfileConfiguration


# what a live ISO keeps that the target can read back: iwd's saved PSKs and
# the networkd units archiso configures the live session with
ISO_IWD_DIR = '/var/lib/iwd'
ISO_NETWORK_DIR = '/etc/systemd/network'


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
				_configure_iwd_standalone(installation)
				installation.enable_service('iwd')
				installation.enable_service('systemd-networkd')

			case NicType.MANUAL:
				for nic in network_config.nics:
					_configure_nic(installation, nic)
				installation.enable_service('systemd-networkd')

		_use_resolved(installation)

		if network_config.dns:
			_configure_dns(installation, network_config.dns)


def _configure_dns(installation: Installer, dns: DnsConfiguration) -> None:
	conf_dir = installation.target / 'etc/systemd/resolved.conf.d'
	conf_dir.mkdir(parents=True, exist_ok=True)
	(conf_dir / 'dns.conf').write_text(dns.as_resolved_config())
	debug(f'Wrote {conf_dir / "dns.conf"}')


def _configure_nm_iwd(installation: Installer) -> None:
	nm_conf_dir = installation.target / 'etc/NetworkManager/conf.d'
	nm_conf_dir.mkdir(parents=True, exist_ok=True)
	(nm_conf_dir / 'wifi_backend.conf').write_text('[device]\nwifi.backend=iwd\n')
	debug(f'Wrote {nm_conf_dir / "wifi_backend.conf"}')


def _configure_iwd_standalone(installation: Installer) -> None:
	# iwd manages wireless only; systemd-networkd handles wired DHCP.
	iwd_conf_dir = installation.target / 'etc/iwd'
	iwd_conf_dir.mkdir(parents=True, exist_ok=True)
	(iwd_conf_dir / 'main.conf').write_text(
		textwrap.dedent("""\
			[General]
			EnableNetworkConfiguration=true

			[Network]
			NameResolvingService=systemd
		""")
	)
	debug(f'Wrote {iwd_conf_dir / "main.conf"}')

	_write_wired_dhcp(installation)


def _write_wired_dhcp(installation: Installer) -> None:
	# Type=ether covers every physical wired NIC without naming one, Kind=!*
	# keeps virtual devices (bridges, veth, ...) out of it
	networkd_dir = installation.target / 'etc/systemd/network'
	networkd_dir.mkdir(parents=True, exist_ok=True)
	(networkd_dir / '20-wired.network').write_text(
		textwrap.dedent("""\
			[Match]
			Type=ether
			Kind=!*

			[Network]
			DHCP=yes
		""")
	)
	debug(f'Wrote {networkd_dir / "20-wired.network"}')


def _copy_iso_network_config(installation: Installer, enable_services: bool = False) -> None:
	# Copy (if any) iwd password and config files
	iwd_dir = LPath(ISO_IWD_DIR)
	if psk_files := list(iwd_dir.glob('*.psk')):
		info(f'Copying {len(psk_files)} iwd profile(s) to target')
		iwd_target = installation.target / iwd_dir.relative_to_root()
		iwd_target.mkdir(parents=True, exist_ok=True)

		for psk in psk_files:
			psk.copy(iwd_target / psk.name, preserve_metadata=True)

		if enable_services:
			# every script runs this after minimal_installation, the target takes packages
			installation.add_additional_packages(ISO_PSK_EXTRA)
			installation.enable_service('iwd')

	# Copy (if any) systemd-networkd config files
	network_dir = LPath(ISO_NETWORK_DIR)
	if netconfigurations := list(network_dir.glob('*')):
		info(f'Copying {len(netconfigurations)} systemd-networkd config(s) to target')
		network_target = installation.target / network_dir.relative_to_root()
		network_target.mkdir(parents=True, exist_ok=True)

		for netconf_file in netconfigurations:
			netconf_file.copy(network_target / netconf_file.name, preserve_metadata=True)

		if enable_services:
			installation.enable_service('systemd-networkd')

	if psk_files or netconfigurations:
		return

	debug('No iwd profiles or systemd-networkd configs found on ISO')
	if not enable_services:
		return

	# a foreign host keeps nothing the target can read: alpine's udhcpc holds
	# its lease in memory and writes no config at all, debian's ifupdown names
	# an interface file Arch has no reader for. Copying is not on the table, so
	# translate the one thing that host was doing (DHCP on the wire) instead of
	# handing over an install with no client and no .network
	warn('Nothing to copy from this host, giving the target wired DHCP instead')
	_write_wired_dhcp(installation)
	installation.enable_service('systemd-networkd')


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

	resolv.symlink_to('/run/systemd/resolve/stub-resolv.conf')
	debug(f'Linked {resolv} to systemd-resolved stub')
