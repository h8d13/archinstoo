import ipaddress
import re
from typing import TYPE_CHECKING, assert_never, override

from archinstoo.lib.menu.list_manager import ListManager
from archinstoo.lib.models.network import DnsConfiguration, DnsProvider, MacAddressPolicy, NetworkConfiguration, Nic, NicType
from archinstoo.lib.network.interfaces import list_interfaces
from archinstoo.lib.tui.curses_menu import EditMenu, SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.prompts import prompt_yes_no
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties

if TYPE_CHECKING:
	from collections.abc import Callable


class ManualNetworkConfig(ListManager[Nic]):
	def __init__(self, prompt: str, preset: list[Nic]) -> None:
		self._actions = [
			'Add interface',
			'Edit interface',
			'Delete interface',
		]

		super().__init__(
			preset,
			[self._actions[0]],
			self._actions[1:],
			prompt,
		)

	@override
	def selected_action_display(self, selection: Nic) -> str:
		return selection.iface or ''

	@override
	def handle_action(self, action: str, entry: Nic | None, data: list[Nic]) -> list[Nic]:
		if action == self._actions[0]:  # add
			iface = self._select_iface(data)
			if iface:
				nic = Nic(iface=iface)
				nic = self._edit_iface(nic)
				data += [nic]
		elif entry:
			if action == self._actions[1]:  # edit interface
				data = [d for d in data if d.iface != entry.iface]
				data.append(self._edit_iface(entry))
			elif action == self._actions[2]:  # delete
				data = [d for d in data if d != entry]

		return data

	def _select_iface(self, data: list[Nic]) -> str | None:
		all_ifaces = list_interfaces().values()
		existing_ifaces = [d.iface for d in data]
		available = set(all_ifaces) - set(existing_ifaces)

		if not available:
			return None

		if not available:
			return None

		items = [MenuItem(i, value=i) for i in available]
		group = MenuItemGroup(items, sort_items=True)

		result = SelectMenu[str](
			group,
			alignment=Alignment.CENTER,
			frame=FrameProperties.min('Interfaces'),
			allow_skip=True,
		).run()

		match result.type_:
			case ResultType.Skip:
				return None
			case ResultType.Selection:
				return result.get_value()
			case ResultType.Reset:
				raise ValueError('Unhandled result type')

	def _get_ip_address(
		self,
		title: str,
		header: str,
		allow_skip: bool,
		multi: bool,
		preset: str | None = None,
	) -> str | None:
		def validator(ip: str | None) -> str | None:
			failure = 'You need to enter a valid IP in IP-config mode'

			if not ip:
				return failure

			ips = ip.split(' ') if multi else [ip]

			try:
				for ip in ips:
					ipaddress.ip_interface(ip)
				return None
			except ValueError:
				return failure

		result = EditMenu(
			title,
			header=header,
			validator=validator,
			allow_skip=allow_skip,
			default_text=preset,
		).input()

		match result.type_:
			case ResultType.Skip:
				return preset
			case ResultType.Selection:
				return result.text()
			case ResultType.Reset:
				raise ValueError('Unhandled result type')

	def _edit_iface(self, edit_nic: Nic) -> Nic:
		iface_name = edit_nic.iface
		modes = ['DHCP (auto detect)', 'IP (static)']
		default_mode = 'DHCP (auto detect)'

		header = f'Select which mode to configure for "{iface_name}"' + '\n'
		items = [MenuItem(m, value=m) for m in modes]
		group = MenuItemGroup(items, sort_items=True)
		group.set_default_by_value(default_mode)

		result = SelectMenu[str](
			group,
			header=header,
			allow_skip=False,
			alignment=Alignment.CENTER,
			frame=FrameProperties.min('Modes'),
		).run()

		match result.type_:
			case ResultType.Selection:
				mode = result.get_value()
			case ResultType.Reset:
				raise ValueError('Unhandled result type')
			case ResultType.Skip:
				raise ValueError('The mode menu should not be skippable')
			case _:
				assert_never(result.type_)

		if mode == 'IP (static)':
			header = f'Enter the IP and subnet for {iface_name} (example: 192.168.0.5/24): ' + '\n'
			ip = self._get_ip_address('IP address', header, False, False)

			header = 'Enter your gateway (router) IP address (leave blank for none)' + '\n'
			gateway = self._get_ip_address('Gateway address', header, True, False)

			display_dns = ' '.join(edit_nic.dns) if edit_nic.dns else None

			header = 'Enter your DNS servers with space separated (leave blank for none)' + '\n'
			dns_servers = self._get_ip_address(
				'DNS servers',
				header,
				True,
				True,
				display_dns,
			)

			dns = []
			if dns_servers is not None:
				dns = dns_servers.split(' ')

			return Nic(iface=iface_name, ip=ip, gateway=gateway, dns=dns, dhcp=False)
		# this will contain network iface names
		return Nic(iface=iface_name)


def _valid_addresses(text: str | None) -> str | None:
	if not text:
		return 'Enter at least one server address'
	for address in text.split():
		try:
			ipaddress.ip_address(address)
		except ValueError:
			return f'{address!r} is not an IPv4 or IPv6 address'
	return None


def _valid_hostname(text: str | None) -> str | None:
	# the name on the resolver's certificate, dns.example.net style; resolved
	# refuses the session when it does not match, so keep the obvious typos out
	if not text or not re.fullmatch(r'[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+', text.lower()):
		return 'Enter the hostname on the server certificate (e.g. dns.quad9.net)'
	return None


def _edit(title: str, header: str, preset: str, validator: Callable[[str | None], str | None]) -> str | None:
	result = EditMenu(title, header=header + '\n', validator=validator, allow_skip=True, default_text=preset or None).input()
	return result.text() if result.type_ == ResultType.Selection else None


def _select_dns(preset: DnsConfiguration | None) -> DnsConfiguration | None:
	# system-wide resolver; None keeps whatever the link hands out
	items = [MenuItem(p.display_msg(), value=p) for p in DnsProvider]
	items.append(MenuItem(text='Use the DNS the network provides', value=None))
	group = MenuItemGroup(items)

	if preset:
		group.set_selected_by_value(preset.provider)
	else:
		group.set_focus_by_value(None)

	result = SelectMenu[DnsProvider | None](
		group,
		header='DNS resolver for the whole system' + '\n',
		alignment=Alignment.CENTER,
		frame=FrameProperties.min('DNS'),
		allow_skip=True,
	).run()

	if result.type_ == ResultType.Skip:
		return preset

	# the "network provides" entry carries None, which get_value() refuses
	provider = result.item().value
	if provider is None:
		return None

	custom = preset if preset and preset.provider is DnsProvider.CUSTOM else None
	servers: list[str] = []
	if provider is DnsProvider.CUSTOM:
		text = _edit('DNS servers', 'Server addresses, space separated', ' '.join(custom.servers) if custom else '', _valid_addresses)
		if text is None:
			return preset
		servers = text.split()

	over_tls = prompt_yes_no('Encrypt lookups with DNS over TLS?' + '\n', preset.over_tls if preset else True)
	if over_tls is None:
		over_tls = True

	tls_name = ''
	if provider is DnsProvider.CUSTOM and over_tls:
		name = _edit('Certificate name', 'Hostname the servers present over TLS', custom.tls_name if custom else '', _valid_hostname)
		if name is None:
			return preset
		tls_name = name.lower()

	return DnsConfiguration(provider, over_tls, servers, tls_name)


def _select_mac_address(preset: MacAddressPolicy) -> MacAddressPolicy:
	items = [MenuItem(m.display_msg(), value=m) for m in MacAddressPolicy]
	group = MenuItemGroup(items)
	group.set_selected_by_value(preset)

	result = SelectMenu[MacAddressPolicy](
		group,
		header='MAC address randomization' + '\n',
		alignment=Alignment.CENTER,
		frame=FrameProperties.min('MAC address'),
		allow_skip=True,
	).run()

	return result.get_value() if result.type_ == ResultType.Selection else preset


def select_network(preset: NetworkConfiguration | None) -> NetworkConfiguration | None:
	# Configure the network on the newly installed system
	items = [MenuItem(n.display_msg(), value=n) for n in NicType]
	items.append(MenuItem(text='None', value=None))
	group = MenuItemGroup(items, sort_items=True)

	if preset:
		group.set_selected_by_value(preset.type)

	result = SelectMenu[NicType](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min('Network configuration'),
		allow_reset=True,
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return None
		case ResultType.Selection:
			config = result.item().value

			if config is None:
				return None

			nics: list[Nic] = []
			if config == NicType.MANUAL:
				preset_nics = preset.nics if preset else []
				nics = ManualNetworkConfig('Configure interfaces', preset_nics).run()

				if not nics:
					return preset

			dns = _select_dns(preset.dns if preset else None)
			mac = _select_mac_address(preset.mac_address if preset else MacAddressPolicy.KEEP)
			return NetworkConfiguration(config, nics, dns, mac)
