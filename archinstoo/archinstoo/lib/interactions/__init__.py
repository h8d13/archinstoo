from .general_conf import (
	add_number_of_parallel_downloads,
	select_additional_packages,
	select_archinstoo_language,
	select_hostname,
	select_ntp,
	select_timezone,
)
from .system_conf import select_driver, select_kernel, select_swap

__all__ = [
	'add_number_of_parallel_downloads',
	'select_additional_packages',
	'select_archinstoo_language',
	'select_driver',
	'select_hostname',
	'select_kernel',
	'select_ntp',
	'select_swap',
	'select_timezone',
]
