import subprocess
import time

from archinstall.lib.output import error, info
from archinstall.lib.tui import EditMenu, MenuItem, MenuItemGroup, SelectMenu, Tui
from archinstall.lib.tui.result import ResultType
from archinstall.lib.tui.types import Alignment, FrameProperties, FrameStyle


def _get_interfaces() -> list[str]:
	result = subprocess.run(
		['iwctl', 'device', 'list'],
		capture_output=True,
		text=True,
	)

	interfaces: list[str] = []

	for line in result.stdout.strip().splitlines():
		# skip header lines and separator
		stripped = line.strip()
		if not stripped or stripped.startswith('-') or stripped.startswith('Device') or 'Powered' in stripped:
			continue

		parts = stripped.split()
		if parts:
			interfaces.append(parts[0])

	return interfaces


def _scan(interface: str) -> None:
	subprocess.run(
		['iwctl', 'station', interface, 'scan'],
		capture_output=True,
	)
	time.sleep(2)


def _get_networks(interface: str) -> list[str]:
	result = subprocess.run(
		['iwctl', 'station', interface, 'get-networks'],
		capture_output=True,
		text=True,
	)

	networks: list[str] = []

	for line in result.stdout.strip().splitlines():
		stripped = line.strip()
		if not stripped or stripped.startswith('-') or stripped.startswith('Network') or 'Security' in stripped:
			continue

		# network name is everything before the last two columns (security, signal)
		# lines look like: "  MyNetwork           psk   ****"
		# but with possible ANSI codes for signal bars
		parts = stripped.rsplit(None, 2)
		if len(parts) >= 2:
			name = parts[0].strip()
			if name and name != '>':
				# strip any leading > marker for connected network
				name = name.lstrip('> ').strip()
				if name:
					networks.append(name)

	return networks


def _connect(interface: str, ssid: str, password: str | None = None) -> bool:
	cmd = ['iwctl', 'station', interface, 'connect', ssid]

	if password:
		cmd += ['--passphrase', password]

	result = subprocess.run(cmd, capture_output=True, text=True)
	return result.returncode == 0


def _select_interface(interfaces: list[str]) -> str | None:
	if len(interfaces) == 1:
		info(f'Using interface: {interfaces[0]}')
		return interfaces[0]

	items = [MenuItem(iface, value=iface) for iface in interfaces]
	group = MenuItemGroup(items)

	result = SelectMenu(
		group,
		header='Select wireless interface',
		frame=FrameProperties('Interfaces', FrameStyle.MIN),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case _:
			return None


def _select_network(networks: list[str]) -> str | None:
	if not networks:
		return None

	items = [MenuItem(ssid, value=ssid) for ssid in networks]
	group = MenuItemGroup(items, sort_items=True, sort_case_sensitive=False)

	result = SelectMenu(
		group,
		header='Select network',
		frame=FrameProperties('Networks', FrameStyle.MIN),
		allow_skip=True,
	).run()

	match result.type_:
		case ResultType.Selection:
			return result.get_value()
		case _:
			return None


def _prompt_password() -> str | None:
	result = EditMenu(
		'Password',
		alignment=Alignment.CENTER,
		allow_skip=True,
		hide_input=True,
	).input()

	match result.type_:
		case ResultType.Selection:
			return result.text() if result.has_item() else None
		case _:
			return None


def wifi() -> None:
	interfaces = _get_interfaces()

	if not interfaces:
		error('No wireless interfaces found. Is iwd running?')
		return

	with Tui():
		interface = _select_interface(interfaces)

	if not interface:
		return

	info(f'Scanning for networks on {interface}...')
	_scan(interface)

	networks = _get_networks(interface)

	if not networks:
		error('No networks found')
		return

	with Tui():
		ssid = _select_network(networks)

	if not ssid:
		return

	with Tui():
		password = _prompt_password()

	info(f'Connecting to {ssid}...')

	if _connect(interface, ssid, password):
		info(f'Connected to {ssid}')
	else:
		error(f'Failed to connect to {ssid}')


wifi()
