import time
from dataclasses import dataclass
from pathlib import Path
from typing import override

from archinstall.lib.exceptions import SysCallError
from archinstall.lib.general import SysCommand
from archinstall.lib.network.wpa_supplicant import WpaSupplicantConfig
from archinstall.lib.output import debug
from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import EditMenu, SelectMenu, Tui
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.result import ResultType


@dataclass
class WifiNetwork:
	bssid: str
	frequency: str
	signal_level: str
	flags: str
	ssid: str

	@override
	def __hash__(self) -> int:
		return hash((self.bssid, self.frequency, self.signal_level, self.flags, self.ssid))

	@staticmethod
	def from_wpa(results: str) -> list['WifiNetwork']:
		entries: list[WifiNetwork] = []

		for line in results.splitlines():
			line = line.strip()
			if not line or line.startswith('bssid'):
				continue

			parts = line.split('\t')
			if len(parts) < 5:
				continue

			wifi = WifiNetwork(
				bssid=parts[0],
				frequency=parts[1],
				signal_level=parts[2],
				flags=parts[3],
				ssid=parts[4] if len(parts) > 4 else '',
			)
			entries.append(wifi)

		return entries


@dataclass
class WifiConfiguredNetwork:
	network_id: int
	ssid: str
	bssid: str
	flags: list[str]

	@classmethod
	def from_wpa_cli_output(cls, list_networks: str) -> list['WifiConfiguredNetwork']:
		lines = list_networks.strip().splitlines()
		if len(lines) > 1:
			lines = lines[1:]  # remove header

		networks = []

		for line in lines:
			line = line.strip()
			parts = line.split('\t')

			if len(parts) < 3:
				continue

			try:
				networks.append(
					WifiConfiguredNetwork(
						network_id=int(parts[0]),
						ssid=parts[1],
						bssid=parts[2],
						flags=[],
					)
				)
			except (ValueError, IndexError):
				debug('Parsing error for network output')

		return networks


@dataclass
class WpaCliResult:
	success: bool
	response: str | None = None
	error: str | None = None


class WifiHandler:
	def __init__(self) -> None:
		self._wpa_config = WpaSupplicantConfig()

	def setup(self) -> bool:
		"""Entry point for wifi setup. Returns True if connected successfully."""
		wifi_iface = self._find_wifi_interface()

		if not wifi_iface:
			debug('No wifi interface found')
			return False

		prompt = tr('No network connection found') + '\n\n'
		prompt += tr('Would you like to connect to a Wifi?')

		result = SelectMenu[bool](
			MenuItemGroup.yes_no(),
			header=prompt,
			allow_skip=True,
		).run()

		if result.type_ != ResultType.Selection:
			return False

		if result.item() == MenuItem.no():
			return False

		return self._setup_wifi(wifi_iface)

	def _find_wifi_interface(self) -> str | None:
		net_path = Path('/sys/class/net')

		for iface in net_path.iterdir():
			maybe_wireless_path = net_path / iface / 'wireless'
			if maybe_wireless_path.is_dir():
				return iface.name

		return None

	def _enable_supplicant(self, wifi_iface: str) -> bool:
		self._wpa_config.load_config()

		result = self._wpa_cli('status')

		if result.success:
			debug('wpa_supplicant already running')
			return True

		if result.error and 'failed to connect to non-global ctrl_ifname'.lower() not in result.error.lower():
			debug('Unexpected wpa_cli failure')
			return False

		debug('wpa_supplicant not running, trying to enable')

		try:
			SysCommand(f'wpa_supplicant -B -i {wifi_iface} -c {self._wpa_config.config_file}')
			result = self._wpa_cli('status')

			if result.success:
				debug('successfully enabled wpa_supplicant')
				return True
			else:
				debug(f'failed to enable wpa_supplicant: {result.error}')
				return False
		except SysCallError as err:
			debug(f'failed to enable wpa_supplicant: {err}')
			return False

	def _setup_wifi(self, wifi_iface: str) -> bool:
		debug('Setting up wifi')

		if not self._enable_supplicant(wifi_iface):
			debug('Failed to enable wpa_supplicant')
			Tui.print(tr('Failed to enable wpa_supplicant'))
			return False

		debug(f'Found wifi interface: {wifi_iface}')
		Tui.print(tr('Scanning wifi networks...'))

		# Scan for networks
		scan_result = self._wpa_cli('scan', wifi_iface)
		if not scan_result.success:
			debug(f'Failed to scan wifi networks: {scan_result.error}')
			Tui.print(tr('Failed to scan wifi networks'))
			return False

		time.sleep(3)  # Wait for scan to complete

		networks = self._get_scan_results(wifi_iface)

		if not networks:
			debug('No networks found')
			Tui.print(tr('No wifi networks found'))
			return False

		# Create menu items for network selection
		items = [MenuItem(n.ssid, value=n) for n in networks if n.ssid]
		if not items:
			Tui.print(tr('No wifi networks found'))
			return False

		group = MenuItemGroup(items)

		result = SelectMenu[WifiNetwork](
			group,
			header=tr('Select wifi network to connect to'),
			allow_skip=True,
		).run()

		if result.type_ != ResultType.Selection or not result.has_item():
			return False

		network: WifiNetwork | None = result.item().value
		if network is None:
			return False

		# Get password
		existing_network = self._wpa_config.get_existing_network(network.ssid)
		existing_psk = existing_network.psk if existing_network else None

		psk = self._prompt_psk(existing_psk)

		if not psk:
			debug('No password specified')
			return False

		self._wpa_config.set_network(network.ssid, psk)
		self._wpa_config.write_config()

		wpa_result = self._wpa_cli('reconfigure')

		if not wpa_result.success:
			debug(f'Failed to reconfigure wpa_supplicant: {wpa_result.error}')
			Tui.print(tr('Failed setting up wifi'))
			return False

		Tui.print(tr('Setting up wifi...'))
		time.sleep(3)

		network_id = self._find_network_id(network.ssid, wifi_iface)

		if network_id is None:
			debug('Failed to find network id')
			Tui.print(tr('Failed setting up wifi'))
			return False

		wpa_result = self._wpa_cli(f'enable {network_id}', wifi_iface)

		if not wpa_result.success:
			debug(f'Failed to enable network: {wpa_result.error}')
			Tui.print(tr('Failed setting up wifi'))
			return False

		Tui.print(tr('Connecting to wifi...'))
		time.sleep(5)

		return True

	def _wpa_cli(self, command: str, iface: str | None = None) -> WpaCliResult:
		cmd = 'wpa_cli'

		if iface:
			cmd += f' -i {iface}'

		cmd += f' {command}'

		try:
			result = SysCommand(cmd).decode()

			if 'FAIL' in result:
				debug(f'wpa_cli returned FAIL: {result}')
				return WpaCliResult(
					success=False,
					error=f'wpa_cli returned a failure: {result}',
				)

			return WpaCliResult(success=True, response=result)
		except SysCallError as err:
			debug(f'error running wpa_cli command: {err}')
			return WpaCliResult(
				success=False,
				error=f'Error running wpa_cli command: {err}',
			)

	def _find_network_id(self, ssid: str, iface: str) -> int | None:
		result = self._wpa_cli('list_networks', iface)

		if not result.success:
			debug(f'Failed to list networks: {result.error}')
			return None

		list_networks = result.response

		if not list_networks:
			debug('No networks found')
			return None

		existing_networks = WifiConfiguredNetwork.from_wpa_cli_output(list_networks)

		for network in existing_networks:
			if network.ssid == ssid:
				return network.network_id

		return None

	def _prompt_psk(self, existing: str | None = None) -> str | None:
		result = EditMenu(
			title=tr('Wifi password'),
			header=tr('Enter wifi password'),
			default_text=existing,
			hide_input=True,
			allow_skip=True,
		).input()

		if result.type_ != ResultType.Selection:
			debug('No password provided, aborting connection')
			return None

		return result.text()

	def _get_scan_results(self, iface: str) -> list[WifiNetwork]:
		debug(f'Retrieving scan results: {iface}')

		try:
			result = self._wpa_cli('scan_results', iface)

			if not result.success:
				debug(f'Failed to retrieve scan results: {result.error}')
				return []

			if not result.response:
				debug('No wifi networks found')
				return []

			networks = WifiNetwork.from_wpa(result.response)

			return networks
		except SysCallError as err:
			debug(f'Unable to retrieve wifi results: {err}')
			return []


wifi_handler = WifiHandler()
