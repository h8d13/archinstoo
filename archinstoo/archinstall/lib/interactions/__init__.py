from .general_conf import (
	add_number_of_parallel_downloads,
	ask_additional_packages_to_install,
	ask_for_a_timezone,
	ask_hostname,
	ask_ntp,
	select_archinstall_language,
)
from .system_conf import ask_for_swap, select_driver, select_kernel

__all__ = [
	'add_number_of_parallel_downloads',
	'ask_additional_packages_to_install',
	'ask_for_a_timezone',
	'ask_for_swap',
	'ask_hostname',
	'ask_ntp',
	'select_archinstall_language',
	'select_driver',
	'select_kernel',
]
