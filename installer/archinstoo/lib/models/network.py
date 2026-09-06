from dataclasses import dataclass, field
from enum import Enum
from typing import NotRequired, Self, TypedDict

# NetworkManager on a desktop gets its tray applet as well
NM_DESKTOP_EXTRA = ['network-manager-applet']

# copy_iso_network_config() carries the ISO's iwd PSKs over when it finds any,
# and the target needs iwd to read them back
ISO_PSK_EXTRA = ['iwd']


class NicType(Enum):
	ISO = 'iso'
	NM = 'nm'
	NM_IWD = 'nm-iwd'
	IWD = 'iwd'
	MANUAL = 'manual'

	@property
	def packages(self) -> list[str]:
		match self:
			case NicType.NM:
				# legacy backend
				return ['networkmanager', 'wpa_supplicant']
			case NicType.NM_IWD:
				# iwd backend, usually for intel devices
				return ['networkmanager', 'iwd']
			case NicType.IWD:
				return ['iwd']
			case NicType.ISO | NicType.MANUAL:
				# systemd-networkd/resolved only, both part of base
				return []

	def display_msg(self) -> str:
		match self:
			case NicType.ISO:
				return 'Copy ISO network configuration to installation'
			case NicType.NM:
				return 'Use Network Manager (default backend)'
			case NicType.NM_IWD:
				return 'Use Network Manager (iwd backend)'
			case NicType.IWD:
				return 'Use iwd standalone (no Network Manager)'
			case NicType.MANUAL:
				return 'Manual configuration'


class DnsProvider(Enum):
	QUAD9 = 'quad9'
	CLOUDFLARE = 'cloudflare'
	GOOGLE = 'google'

	@property
	def servers(self) -> list[str]:
		match self:
			case DnsProvider.QUAD9:
				return ['9.9.9.9', '149.112.112.112', '2620:fe::fe', '2620:fe::9']
			case DnsProvider.CLOUDFLARE:
				return ['1.1.1.1', '1.0.0.1', '2606:4700:4700::1111', '2606:4700:4700::1001']
			case DnsProvider.GOOGLE:
				return ['8.8.8.8', '8.8.4.4', '2001:4860:4860::8888', '2001:4860:4860::8844']

	@property
	def tls_name(self) -> str:
		# the certificate name resolved validates a DNS-over-TLS session against
		match self:
			case DnsProvider.QUAD9:
				return 'dns.quad9.net'
			case DnsProvider.CLOUDFLARE:
				return 'cloudflare-dns.com'
			case DnsProvider.GOOGLE:
				return 'dns.google'

	def display_msg(self) -> str:
		match self:
			case DnsProvider.QUAD9:
				return 'Quad9 (malware blocking, no logging)'
			case DnsProvider.CLOUDFLARE:
				return 'Cloudflare (1.1.1.1)'
			case DnsProvider.GOOGLE:
				return 'Google (8.8.8.8)'


class _DnsSerialization(TypedDict):
	provider: str
	over_tls: bool


@dataclass
class DnsConfiguration:
	provider: DnsProvider
	over_tls: bool = True

	def json(self) -> _DnsSerialization:
		return {'provider': self.provider.value, 'over_tls': self.over_tls}

	@classmethod
	def parse_arg(cls, arg: _DnsSerialization) -> Self:
		return cls(DnsProvider(arg['provider']), arg.get('over_tls', True))

	def as_resolved_config(self) -> str:
		# a resolved.conf.d drop-in. Domains=~. routes every lookup here ahead
		# of the per-link servers DHCP hands out, which is what makes the pick
		# system-wide rather than a fallback
		# https://wiki.archlinux.org/title/Systemd-resolved#DNS_over_TLS
		suffix = f'#{self.provider.tls_name}' if self.over_tls else ''
		servers = ' '.join(f'{ip}{suffix}' for ip in self.provider.servers)

		lines = ['[Resolve]', f'DNS={servers}']
		if self.over_tls:
			lines.append('DNSOverTLS=yes')
		lines.append('Domains=~.')

		return '\n'.join(lines) + '\n'


class MacAddressPolicy(Enum):
	# keep: hardware address. stable: one address per network, so DHCP leases
	# and captive portals still recognise the machine. random: new address per
	# connection (per boot on the networkd paths)
	KEEP = 'keep'
	STABLE = 'stable'
	RANDOM = 'random'

	def display_msg(self) -> str:
		match self:
			case MacAddressPolicy.KEEP:
				return 'Keep the hardware address'
			case MacAddressPolicy.STABLE:
				return 'Stable per network (recommended)'
			case MacAddressPolicy.RANDOM:
				return 'Random per connection'

	def as_nm_config(self) -> str:
		# scan randomisation is NM's default already; cloned-mac-address is the
		# part that carries over into the connection itself
		# https://wiki.archlinux.org/title/NetworkManager#Configuring_MAC_address_randomization
		connection = f'wifi.cloned-mac-address={self.value}\nethernet.cloned-mac-address={self.value}\n'
		return f'[device]\nwifi.scan-rand-mac-address=yes\n\n[connection]\n{connection}'

	def as_iwd_config(self) -> str:
		# iwd's own knob for wireless; per-network is what NM calls stable
		mode = 'network' if self is MacAddressPolicy.STABLE else 'once'
		return f'AddressRandomization={mode}\n'

	def as_link_config(self) -> str:
		# systemd .link for what udev brings up; there is no per-network notion
		# here, so stable leaves wired links alone
		# https://wiki.archlinux.org/title/MAC_address_spoofing#systemd-networkd
		return '[Match]\nOriginalName=*\n\n[Link]\nMACAddressPolicy=random\n'


class _NicSerialization(TypedDict):
	iface: str | None
	ip: str | None
	dhcp: bool
	gateway: str | None
	dns: list[str]


@dataclass
class Nic:
	iface: str | None = None
	ip: str | None = None
	dhcp: bool = True
	gateway: str | None = None
	dns: list[str] = field(default_factory=list)

	def table_data(self) -> dict[str, str | bool | list[str]]:
		return {
			'iface': self.iface or '',
			'ip': self.ip or '',
			'dhcp': self.dhcp,
			'gateway': self.gateway or '',
			'dns': self.dns,
		}

	def json(self) -> _NicSerialization:
		return {
			'iface': self.iface,
			'ip': self.ip,
			'dhcp': self.dhcp,
			'gateway': self.gateway,
			'dns': self.dns,
		}

	@classmethod
	def parse_arg(cls, arg: _NicSerialization) -> Self:
		return cls(
			iface=arg.get('iface', None),
			ip=arg.get('ip', None),
			dhcp=arg.get('dhcp', True),
			gateway=arg.get('gateway', None),
			dns=arg.get('dns', []),
		)

	def as_systemd_config(self) -> str:
		match: list[tuple[str, str]] = []
		network: list[tuple[str, str]] = []

		if self.iface:
			match.append(('Name', self.iface))

		if self.dhcp:
			network.append(('DHCP', 'yes'))
		else:
			if self.ip:
				network.append(('Address', self.ip))
			if self.gateway:
				network.append(('Gateway', self.gateway))
			network.extend(('DNS', dns) for dns in self.dns)

		config = {'Match': match, 'Network': network}

		config_str = ''
		for top, entries in config.items():
			config_str += f'[{top}]\n'
			config_str += '\n'.join([f'{k}={v}' for k, v in entries])
			config_str += '\n\n'

		return config_str


class _NetworkConfigurationSerialization(TypedDict):
	type: str
	nics: NotRequired[list[_NicSerialization]]
	dns: NotRequired[_DnsSerialization]
	mac_address: NotRequired[str]


@dataclass
class NetworkConfiguration:
	type: NicType
	nics: list[Nic] = field(default_factory=list)
	# system-wide resolver, any type: every path runs systemd-resolved
	dns: DnsConfiguration | None = None
	mac_address: MacAddressPolicy = MacAddressPolicy.KEEP

	def json(self) -> _NetworkConfigurationSerialization:
		config: _NetworkConfigurationSerialization = {'type': self.type.value}
		if self.nics:
			config['nics'] = [n.json() for n in self.nics]
		if self.dns:
			config['dns'] = self.dns.json()
		if self.mac_address is not MacAddressPolicy.KEEP:
			config['mac_address'] = self.mac_address.value

		return config

	@classmethod
	def parse_arg(cls, config: _NetworkConfigurationSerialization) -> Self | None:
		nic_type = config.get('type', None)
		if not nic_type:
			return None

		nics: list[Nic] = []
		if NicType(nic_type) == NicType.MANUAL:
			# a manual config with no interfaces configures nothing
			nics = [Nic.parse_arg(n) for n in config.get('nics', [])]
			if not nics:
				return None

		dns = DnsConfiguration.parse_arg(dns_arg) if (dns_arg := config.get('dns')) else None
		mac = MacAddressPolicy(config.get('mac_address', MacAddressPolicy.KEEP.value))

		return cls(NicType(nic_type), nics, dns, mac)
