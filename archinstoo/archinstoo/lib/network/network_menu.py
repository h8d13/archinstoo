import ipaddress
from typing import assert_never, override

from archinstoo.lib.menu.abstract_menu import AbstractSubMenu
from archinstoo.lib.menu.list_manager import ListManager
from archinstoo.lib.models.network import NetworkConfiguration, Nic, NicType
from archinstoo.lib.network.utils import list_interfaces
from archinstoo.lib.output import FormattedOutput
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import EditMenu, SelectMenu
from archinstoo.lib.tui.menu_item import MenuItem, MenuItemGroup
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.tui.types import Alignment, FrameProperties


class ManualNetworkConfig(ListManager[Nic]):
	def __init__(self, prompt: str, preset: list[Nic]):
		self._actions = [
			tr('Add interface'),
			tr('Edit interface'),
			tr('Delete interface'),
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

		items = [MenuItem(i, value=i) for i in available]
		group = MenuItemGroup(items, sort_items=True)

		result = SelectMenu[str](
			group,
			alignment=Alignment.CENTER,
			frame=FrameProperties.min(tr('Interfaces')),
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
			failure = tr('You need to enter a valid IP in IP-config mode')

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

		header = tr('Select which mode to configure for "{}"').format(iface_name) + '\n'
		items = [MenuItem(m, value=m) for m in modes]
		group = MenuItemGroup(items, sort_items=True)
		group.set_default_by_value(default_mode)

		result = SelectMenu[str](
			group,
			header=header,
			allow_skip=False,
			alignment=Alignment.CENTER,
			frame=FrameProperties.min(tr('Modes')),
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
			header = tr('Enter the IP and subnet for {} (example: 192.168.0.5/24): ').format(iface_name) + '\n'
			ip = self._get_ip_address(tr('IP address'), header, False, False)

			header = tr('Enter your gateway (router) IP address (leave blank for none)') + '\n'
			gateway = self._get_ip_address(tr('Gateway address'), header, True, False)

			display_dns = ' '.join(edit_nic.dns) if edit_nic.dns else None

			header = tr('Enter your DNS servers with space separated (leave blank for none)') + '\n'
			dns_servers = self._get_ip_address(
				tr('DNS servers'),
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


def _select_nic_type(preset: NicType) -> NicType:
	items = [MenuItem(n.display_msg(), value=n) for n in NicType]
	group = MenuItemGroup(items, sort_items=True)
	group.set_focus_by_value(preset)

	result = SelectMenu[NicType](
		group,
		alignment=Alignment.CENTER,
		frame=FrameProperties.min(tr('Network configuration')),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Selection:
			return result.get_value()
		case ResultType.Reset:
			raise ValueError('Unhandled result type')


def _select_interfaces(preset: list[Nic]) -> list[Nic]:
	return ManualNetworkConfig(tr('Configure interfaces'), preset).run()


class NetworkMenu(AbstractSubMenu[NetworkConfiguration]):
	def __init__(self, config: NetworkConfiguration):
		self._net_conf = config
		menu_options = self._define_menu_options()

		self._item_group = MenuItemGroup(menu_options, sort_items=False, checkmarks=True)
		super().__init__(
			self._item_group,
			config=self._net_conf,
		)

	def _define_menu_options(self) -> list[MenuItem]:
		return [
			MenuItem(
				text=tr('Type'),
				action=self._select_type,
				value=self._net_conf.type,
				preview_action=self._prev_network,
				key='type',
			),
			MenuItem(
				text=tr('Interfaces'),
				action=_select_interfaces,
				value=self._net_conf.nics,
				preview_action=self._prev_network,
				key='nics',
				enabled=self._net_conf.type == NicType.MANUAL,
			),
		]

	def _select_type(self, preset: NicType) -> NicType:
		result = _select_nic_type(preset)
		self._item_group.find_by_key('nics').enabled = result == NicType.MANUAL
		return result

	def _prev_network(self, item: MenuItem) -> str | None:
		nic_type = NicType(self._item_group.find_by_key('type').value)
		if nic_type == NicType.MANUAL:
			nics: list[Nic] = self._item_group.find_by_key('nics').value or []
			if nics:
				return FormattedOutput.as_table(nics)
		return f'{tr("Network configuration")}:\n{nic_type.display_msg()}'

	@override
	def run(self, additional_title: str | None = None) -> NetworkConfiguration:
		super().run(additional_title=additional_title)
		return self._net_conf
