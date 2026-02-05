import signal
import socket
import ssl
import struct
import time
from types import FrameType, TracebackType
from typing import Self, cast
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from archinstoo.lib.exceptions import DownloadTimeout


class DownloadTimer:
	"""
	Context manager for timing downloads with timeouts.
	"""

	def __init__(self, timeout: int = 5):
		"""
		Args:
			timeout:
				The download timeout in seconds. The DownloadTimeout exception
				will be raised in the context after this many seconds.
		"""
		self.time: float | None = None
		self.start_time: float | None = None
		self.timeout = timeout
		self.previous_handler = None
		self.previous_timer: int | None = None

	def raise_timeout(self, signl: int, frame: FrameType | None) -> None:
		"""
		Raise the DownloadTimeout exception.
		"""
		raise DownloadTimeout(f'Download timed out after {self.timeout} second(s).')

	def __enter__(self) -> Self:
		if self.timeout > 0:
			self.previous_handler = signal.signal(signal.SIGALRM, self.raise_timeout)  # type: ignore[assignment]
			self.previous_timer = signal.alarm(self.timeout)

		self.start_time = time.time()
		return self

	def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
		if self.start_time:
			time_delta = time.time() - self.start_time
			signal.alarm(0)
			self.time = time_delta
			if self.timeout > 0:
				signal.signal(signal.SIGALRM, self.previous_handler)

				previous_timer = self.previous_timer
				if previous_timer and previous_timer > 0:
					remaining_time = int(previous_timer - time_delta)
					# The alarm should have been raised during the download.
					if remaining_time <= 0:
						signal.raise_signal(signal.SIGALRM)
					else:
						signal.alarm(remaining_time)
		self.start_time = None


def get_hw_addr(ifname: str) -> str:
	import fcntl

	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	ret = fcntl.ioctl(s.fileno(), 0x8927, struct.pack('256s', bytes(ifname, 'utf-8')[:15]))
	return ':'.join(f'{b:02x}' for b in ret[18:24])


def list_interfaces(skip_loopback: bool = True) -> dict[str, str]:
	interfaces = {}

	for _index, iface in socket.if_nameindex():
		if skip_loopback and iface == 'lo':
			continue

		mac = get_hw_addr(iface).replace(':', '-').lower()
		interfaces[mac] = iface

	return interfaces


def fetch_data_from_url(url: str, params: dict[str, str] | None = None, timeout: int = 30) -> str:
	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode = ssl.CERT_NONE

	if params is not None:
		encoded = urlencode(params)
		full_url = f'{url}?{encoded}'
	else:
		full_url = url

	try:
		response = urlopen(full_url, context=ssl_context, timeout=timeout)
		data = response.read().decode('UTF-8')
		return cast(str, data)
	except URLError as e:
		raise ValueError(f'Unable to fetch data from url: {url}\n{e}')
	except Exception as e:
		raise ValueError(f'Unexpected error when parsing response: {e}')
