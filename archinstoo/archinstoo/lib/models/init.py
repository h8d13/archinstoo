from enum import Enum


class InitHooks(Enum):
	Busybox = 'busybox'
	Systemd = 'systemd'

	def display_name(self) -> str:
		match self:
			case InitHooks.Busybox:
				return 'Busybox'
			case InitHooks.Systemd:
				return 'Systemd'

	def json(self) -> str:
		return self.value
