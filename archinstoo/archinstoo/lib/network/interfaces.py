import socket
import struct


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
