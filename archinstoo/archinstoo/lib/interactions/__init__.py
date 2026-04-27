from .general_conf import (
	select_additional_packages,
	select_archinstoo_language,
	select_hostname,
	select_ntp,
	select_timezone,
)
from .system_conf import select_firmware, select_kernel, select_swap

__all__ = [
	'select_additional_packages',
	'select_archinstoo_language',
	'select_firmware',
	'select_hostname',
	'select_kernel',
	'select_ntp',
	'select_swap',
	'select_timezone',
]
