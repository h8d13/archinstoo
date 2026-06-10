from pathlib import Path
from subprocess import CalledProcessError
from typing import ClassVar

from archinstoo.lib.general import run
from archinstoo.lib.models.device import Fido2Device
from archinstoo.lib.output import error


class Fido2:
	_loaded: bool = False
	_devices: ClassVar[list[Fido2Device]] = []

	@classmethod
	def get_cryptenroll_devices(cls, reload: bool = False) -> list[Fido2Device]:
		# Lists FIDO2 tokens systemd-cryptenroll can bind a keyslot to.
		# Output is a human readable table; columns are located via the
		# header since PRODUCT values contain spaces:
		#
		# PATH         MANUFACTURER PRODUCT
		# /dev/hidraw1 Yubico       YubiKey OTP+FIDO+CCID
		#
		# Cached: menu previews re-run this on every redraw.
		if cls._loaded and not reload:
			return cls._devices

		try:
			ret = run(['systemd-cryptenroll', '--fido2-device=list'])
		except (CalledProcessError, FileNotFoundError) as e:
			error(f'failed to list FIDO2 tokens (is libfido2 installed?): {e}')
			return []

		manufacturer_pos = 0
		product_pos = 0
		devices: list[Fido2Device] = []

		for line in ret.stdout.decode().splitlines():
			if '/dev' not in line:
				manufacturer_pos = line.find('MANUFACTURER')
				product_pos = line.find('PRODUCT')
				continue

			path = line[:manufacturer_pos].rstrip()
			manufacturer = line[manufacturer_pos:product_pos].rstrip()
			product = line[product_pos:].rstrip()

			devices.append(Fido2Device(Path(path), manufacturer, product))

		cls._loaded = True
		cls._devices = devices

		return cls._devices
