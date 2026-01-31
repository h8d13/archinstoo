import random
import select
import socket
import struct
import time


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
	"""ICMP ping, returns latency in ms or -1 on failure."""
	watchdog = select.epoll()
	started = time.time()
	random_identifier = f'archinstall-{random.randint(1000, 9999)}'.encode()

	icmp_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
	watchdog.register(icmp_socket, select.EPOLLIN | select.EPOLLHUP)

	icmp_packet = _build_icmp(random_identifier)
	icmp_socket.sendto(icmp_packet, (hostname, 0))
	latency = -1

	while latency == -1 and time.time() - started < timeout:
		try:
			for _fileno, _event in watchdog.poll(0.1):
				response, _ = icmp_socket.recvfrom(1024)
				icmp_type = struct.unpack('!B', response[20:21])[0]
				if icmp_type == 0 and response[-len(random_identifier) :] == random_identifier:
					latency = round((time.time() - started) * 1000)
					break
		except OSError:
			break

	icmp_socket.close()
	return latency
