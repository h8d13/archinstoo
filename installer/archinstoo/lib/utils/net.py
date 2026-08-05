import random
import select
import shutil
import signal
import socket
import ssl
import struct
import time
from typing import TYPE_CHECKING, Self
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from archinstoo.lib.exceptions import DownloadTimeout

if TYPE_CHECKING:
	from collections.abc import Callable
	from pathlib import Path
	from types import FrameType, TracebackType


def _calc_checksum(icmp_packet: bytes) -> int:
	checksum = 0
	for i in range(0, len(icmp_packet), 2):
		checksum += (icmp_packet[i] << 8) + (struct.unpack('B', icmp_packet[i + 1 : i + 2])[0] if len(icmp_packet[i + 1 : i + 2]) else 0)
	checksum = (checksum >> 16) + (checksum & 0xFFFF)
	return ~checksum & 0xFFFF


def _build_icmp(payload: bytes) -> bytes:
	icmp_packet = struct.pack('!BBHHH', 8, 0, 0, 0, 1) + payload
	checksum = _calc_checksum(icmp_packet)
	return struct.pack('!BBHHH', 8, 0, checksum, 0, 1) + payload


def ping(hostname: str, timeout: int = 5) -> int:
	# ICMP ping, returns latency in ms or -1 on failure.
	watchdog = select.epoll()
	started = time.monotonic()
	random_identifier = f'archinstoo-{random.randint(1000, 9999)}'.encode()  # noqa: S311 - ICMP echo id, not for crypto

	icmp_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
	watchdog.register(icmp_socket, select.EPOLLIN | select.EPOLLHUP)

	icmp_packet = _build_icmp(random_identifier)
	icmp_socket.sendto(icmp_packet, (hostname, 0))
	latency = -1

	while latency == -1 and time.monotonic() - started < timeout:
		try:
			for _fileno, _event in watchdog.poll(0.1):
				response, _ = icmp_socket.recvfrom(1024)
				icmp_type = struct.unpack('!B', response[20:21])[0]
				if icmp_type == 0 and response[-len(random_identifier) :] == random_identifier:
					latency = round((time.monotonic() - started) * 1000)
					break
		except OSError:
			break

	icmp_socket.close()
	return latency


class DownloadTimer:
	# Context manager for timing downloads with timeouts.
	def __init__(self, timeout: int = 5):
		# Args:
		# timeout:
		# The download timeout in seconds. The DownloadTimeout exception
		# will be raised in the context after this many seconds.
		self.time: float | None = None
		self.start_time: float | None = None
		self.timeout = timeout
		self.previous_handler: Callable[[int, FrameType | None], object] | int | signal.Handlers | None = None
		self.previous_timer: int | None = None

	def raise_timeout(self, _signl: int, _frame: FrameType | None) -> None:
		# Raise the DownloadTimeout with time
		raise DownloadTimeout(f'Download timed out after {self.timeout} second(s).')

	def __enter__(self) -> Self:
		if self.timeout > 0:
			self.previous_handler = signal.signal(signal.SIGALRM, self.raise_timeout)
			self.previous_timer = signal.alarm(self.timeout)

		self.start_time = time.monotonic()
		return self

	def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
		if self.start_time:
			time_delta = time.monotonic() - self.start_time
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


def fetch_data_from_url(url: str, params: dict[str, str] | None = None, timeout: int = 30) -> str:
	from urllib.parse import urlparse

	if urlparse(url).scheme not in ('http', 'https'):
		raise ValueError(f'Refusing to fetch non-http(s) url: {url}')

	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode = ssl.CERT_NONE

	if params is not None:
		encoded = urlencode(params)
		full_url = f'{url}?{encoded}'
	else:
		full_url = url

	try:
		response = urlopen(full_url, context=ssl_context, timeout=timeout)  # noqa: S310 - scheme restricted above
		data: str = response.read().decode('UTF-8')
		return data
	except URLError as e:
		raise ValueError(f'Unable to fetch data from url: {url}\n{e}')
	except Exception as e:
		raise ValueError(f'Unexpected error when parsing response: {e}')


def download_file_from_url(url: str, dest: Path, timeout: int = 30) -> None:
	# binary sibling of fetch_data_from_url: streams the response to disk instead
	# of decoding to text, for package/archive downloads
	from urllib.parse import urlparse

	if urlparse(url).scheme not in ('http', 'https'):
		raise ValueError(f'Refusing to fetch non-http(s) url: {url}')

	ssl_context = ssl.create_default_context()
	ssl_context.check_hostname = False
	ssl_context.verify_mode = ssl.CERT_NONE

	try:
		with urlopen(url, context=ssl_context, timeout=timeout) as resp, dest.open('wb') as out:  # noqa: S310 - scheme restricted above
			shutil.copyfileobj(resp, out)
	except URLError as e:
		raise ValueError(f'Unable to download from url: {url}\n{e}')
