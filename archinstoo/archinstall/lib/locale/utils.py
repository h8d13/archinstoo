from pathlib import Path

from ..exceptions import ServiceException, SysCallError
from ..general import SysCommand
from ..output import error
from ..utils.env import Os


def list_keyboard_languages() -> list[str]:
	return (
		SysCommand(
			'localectl --no-pager list-keymaps',
			environment_vars={'SYSTEMD_COLORS': '0'},
		)
		.decode()
		.splitlines()
	)


def list_locales() -> list[str]:
	locales = []

	with open('/usr/share/i18n/SUPPORTED') as file:
		for line in file:
			if line != 'C.UTF-8 UTF-8\n':
				locales.append(line.rstrip())

	return locales


def verify_keyboard_layout(layout: str) -> bool:
	for language in list_keyboard_languages():
		if layout.lower() == language.lower():
			return True
	return False


def list_x11_keyboard_languages() -> list[str]:
	return (
		SysCommand(
			'localectl --no-pager list-x11-keymap-layouts',
			environment_vars={'SYSTEMD_COLORS': '0'},
		)
		.decode()
		.splitlines()
	)


def verify_x11_keyboard_layout(layout: str) -> bool:
	for language in list_x11_keyboard_languages():
		if layout.lower() == language.lower():
			return True
	return False


def get_kb_layout() -> str:
	try:
		lines = (
			SysCommand(
				'localectl --no-pager status',
				environment_vars={'SYSTEMD_COLORS': '0'},
			)
			.decode()
			.splitlines()
		)
	except Exception:
		return ''

	vcline = ''
	for line in lines:
		if 'VC Keymap: ' in line:
			vcline = line

	if vcline == '':
		return ''

	layout = vcline.split(': ')[1]
	if not verify_keyboard_layout(layout):
		return ''

	return layout


def set_kb_layout(locale: str) -> bool:
	if Os.running_from_host():
		# Skip when running from host - no need to change host keymap
		# The target installation keymap is set via installer.set_vconsole()
		return True

	if len(locale.strip()):
		if not verify_keyboard_layout(locale):
			error(f'Invalid keyboard locale specified: {locale}')
			return False

		try:
			SysCommand(f'localectl set-keymap {locale}')
		except SysCallError as err:
			raise ServiceException(f"Unable to set locale '{locale}' for console: {err}")

		return True

	return False


def list_console_fonts() -> list[str]:
	font_dir = Path('/usr/share/kbd/consolefonts')
	fonts: list[str] = []

	if font_dir.exists():
		for f in font_dir.iterdir():
			# skip documentation files
			if f.name.startswith('README'):
				continue
			name = f.name
			for suffix in ('.psfu.gz', '.psf.gz', '.gz'):
				if name.endswith(suffix):
					name = name[: -len(suffix)]
					break
			fonts.append(name)

	return sorted(fonts, key=lambda x: (len(x), x))


def list_timezones() -> list[str]:
	return (
		SysCommand(
			'timedatectl --no-pager list-timezones',
			environment_vars={'SYSTEMD_COLORS': '0'},
		)
		.decode()
		.splitlines()
	)
