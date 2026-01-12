from archinstall.lib.network import wifi_handler
from archinstall.lib.networking import ping
from archinstall.lib.output import info
from archinstall.tui import Tui


def wifi() -> None:
	"""Connect to a wifi network using wpa_supplicant."""
	with Tui():
		if wifi_handler.setup():
			# Verify connection
			try:
				ping('1.1.1.1')
				info('Successfully connected to wifi!')
			except OSError:
				info('Wifi configured but no internet connectivity yet.')
		else:
			info('Wifi setup cancelled or failed.')


wifi()
