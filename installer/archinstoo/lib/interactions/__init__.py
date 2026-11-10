from .general_conf import (
	select_hostname,
	select_ntp,
	select_timezone,
)
from .system_conf import select_firmware

__all__ = [
	'select_firmware',
	'select_hostname',
	'select_ntp',
	'select_timezone',
]
