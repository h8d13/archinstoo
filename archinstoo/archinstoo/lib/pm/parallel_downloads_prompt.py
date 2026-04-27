from typing import assert_never

from archinstoo.lib.pathnames import PACMAN_CONF
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import EditMenu
from archinstoo.lib.tui.result import ResultType


def add_number_of_parallel_downloads(preset: int | None = None) -> int | None:
	max_recommended = 5

	header = tr('This option enables the number of parallel downloads that can occur during package downloads') + '\n'
	header += tr('Enter the number of parallel downloads to be enabled.\n\nNote:\n')
	header += tr(' - Maximum recommended value : {} ( Allows {} parallel downloads at a time )').format(max_recommended, max_recommended) + '\n'
	header += tr(' - Disable/Default : 0 ( Disables parallel downloading, allows only 1 download at a time )\n')

	def validator(s: str | None) -> str | None:
		if s is not None:
			try:
				value = int(s)
				if value >= 0:
					return None
			except Exception:
				pass

		return tr('Invalid download number')

	result = EditMenu(
		tr('Number downloads'),
		header=header,
		allow_skip=True,
		allow_reset=True,
		validator=validator,
		default_text=str(preset) if preset is not None else None,
	).input()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return 0
		case ResultType.Selection:
			downloads: int = int(result.text())
		case _:
			assert_never(result.type_)

	with PACMAN_CONF.open() as f:
		pacman_conf = f.read().split('\n')

	with PACMAN_CONF.open('w') as fwrite:
		for line in pacman_conf:
			if 'ParallelDownloads' in line:
				fwrite.write(f'ParallelDownloads = {downloads}\n')
			else:
				fwrite.write(f'{line}\n')

	return downloads
