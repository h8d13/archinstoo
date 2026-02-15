from enum import Enum


class InitHooks(Enum):
	Busybox = 'busybox'
	Systemd = 'systemd'

	def display_name(self) -> str:
		match self:
			case InitHooks.Busybox:
				return 'Busybox (encrypt)'
			case InitHooks.Systemd:
				return 'Systemd (sd-encrypt)'

	def json(self) -> str:
		return self.value
