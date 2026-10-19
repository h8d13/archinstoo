from pathlib import Path
from typing import ClassVar

from archinstoo.lib.models.device import Fido2Device
from archinstoo.lib.output import debug

# Module-level so tests can point the sweep at a synthetic tree
_HIDRAW = Path('/sys/class/hidraw')
# HID usage page the FIDO Alliance registered for CTAP authenticators
_FIDO_USAGE_PAGE = 0xF1D0


def _is_fido(descriptor: bytes) -> bool:
	# walk the HID report descriptor's items for a Usage Page of 0xF1D0,
	# the same test libfido2 runs on Linux to tell a token from a keyboard
	i = 0
	while i < len(descriptor):
		prefix = descriptor[i]
		if prefix == 0xFE:
			# long item: size byte, tag byte, then the data
			if i + 1 >= len(descriptor):
				return False
			i += 3 + descriptor[i + 1]
			continue

		size = (0, 1, 2, 4)[prefix & 0x03]
		data = descriptor[i + 1 : i + 1 + size]
		# global item, tag 0: Usage Page
		if (
			prefix & 0xFC == 0x04
			and int.from_bytes(data, 'little') == _FIDO_USAGE_PAGE
		):
			return True
		i += 1 + size
	return False


def _read(path: Path) -> str:
	try:
		# USB string descriptors are vendor filled, like SMBIOS ones
		return path.read_text(errors='replace').strip()
	except OSError:
		return ''


def _describe(hid: Path) -> tuple[str, str]:
	# hidrawN/device is the HID device; for USB its parent is the interface
	# and the one above that the USB device, which has the string descriptors
	usb = hid.parent.parent
	manufacturer = _read(usb / 'manufacturer')
	product = _read(usb / 'product')
	if not product:
		# bluetooth/i2c tokens: only the combined HID_NAME is known
		for line in _read(hid / 'uevent').splitlines():
			key, _, value = line.partition('=')
			if key == 'HID_NAME':
				product = value
	return manufacturer, product


class Fido2:
	_loaded: bool = False
	_devices: ClassVar[list[Fido2Device]] = []

	@classmethod
	def get_devices(cls, reload: bool = False) -> list[Fido2Device]:
		# Lists FIDO2 tokens straight from the kernel's hidraw nodes, so
		# the host needs no systemd-cryptenroll/libfido2 to offer one; the
		# enrollment itself runs in the target.
		# Cached: menu previews re-run this on every redraw.
		if cls._loaded and not reload:
			return cls._devices

		devices: list[Fido2Device] = []
		for node in sorted(_HIDRAW.glob('hidraw*')):
			hid = (node / 'device').resolve()
			try:
				descriptor = (hid / 'report_descriptor').read_bytes()
			except OSError as e:
				debug(f'skipping {node.name}: {e}')
				continue
			if _is_fido(descriptor):
				devices.append(
					Fido2Device(
						Path('/dev') / node.name,
						*_describe(hid),
					)
				)

		cls._loaded = True
		cls._devices = devices

		return cls._devices
