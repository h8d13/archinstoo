import shutil
from pathlib import Path

from ..exceptions import ServiceException, SysCallError
from ..general import SysCommand
from ..output import error
from ..utils.env import running_from_host


def _list_keymaps_from_files() -> list[str]:
	"""Fallback: list keymaps from console-setup or kbd files."""
	keymaps = []

	# Check kbd keymaps directory (Arch, most distros)
	kbd_paths = [
		Path('/usr/share/kbd/keymaps'),
		Path('/usr/share/keymaps'),  # Alpine
	]

	for kbd_path in kbd_paths:
		if kbd_path.exists():
			for path in kbd_path.rglob('*.map.gz'):
				keymaps.append(path.stem.replace('.map', ''))
			for path in kbd_path.rglob('*.map'):
				keymaps.append(path.stem)
			break

	return sorted(set(keymaps))


def list_keyboard_languages() -> list[str]:
	# Try localectl first (systemd)
	if shutil.which('localectl'):
		return (
			SysCommand(
				'localectl --no-pager list-keymaps',
				environment_vars={'SYSTEMD_COLORS': '0'},
			)
			.decode()
			.splitlines()
		)

	# Fallback: read from keymap files
	return _list_keymaps_from_files()


def list_locales() -> list[str]:
	locales = []

	supported_path = Path('/usr/share/i18n/SUPPORTED')
	if supported_path.exists():
		for line in supported_path.read_text().splitlines():
			if line and line != 'C.UTF-8 UTF-8':
				locales.append(line.rstrip())
	else:
		# Fallback: list from locale.gen or provide common defaults
		locale_gen = Path('/etc/locale.gen')
		if locale_gen.exists():
			for line in locale_gen.read_text().splitlines():
				line = line.strip()
				if line and not line.startswith('#'):
					locales.append(line)

		# If still empty, provide common defaults
		if not locales:
			locales = [
				'en_US.UTF-8 UTF-8',
				'en_GB.UTF-8 UTF-8',
				'de_DE.UTF-8 UTF-8',
				'fr_FR.UTF-8 UTF-8',
				'es_ES.UTF-8 UTF-8',
				'it_IT.UTF-8 UTF-8',
				'pt_BR.UTF-8 UTF-8',
				'ru_RU.UTF-8 UTF-8',
				'zh_CN.UTF-8 UTF-8',
				'ja_JP.UTF-8 UTF-8',
			]

	return locales


def verify_keyboard_layout(layout: str) -> bool:
	for language in list_keyboard_languages():
		if layout.lower() == language.lower():
			return True
	return False


def _list_x11_layouts_from_files() -> list[str]:
	"""Fallback: list X11 layouts from xkb rules."""
	layouts = []

	rules_paths = [
		Path('/usr/share/X11/xkb/rules/base.lst'),
		Path('/usr/share/X11/xkb/rules/evdev.lst'),
	]

	for rules_path in rules_paths:
		if rules_path.exists():
			in_layout_section = False
			for line in rules_path.read_text().splitlines():
				if line.strip() == '! layout':
					in_layout_section = True
					continue
				if line.startswith('!'):
					in_layout_section = False
					continue
				if in_layout_section and line.strip():
					parts = line.split()
					if parts:
						layouts.append(parts[0])
			break

	return sorted(set(layouts))


def list_x11_keyboard_languages() -> list[str]:
	# Try localectl first (systemd)
	if shutil.which('localectl'):
		return (
			SysCommand(
				'localectl --no-pager list-x11-keymap-layouts',
				environment_vars={'SYSTEMD_COLORS': '0'},
			)
			.decode()
			.splitlines()
		)

	# Fallback: read from xkb rules files
	return _list_x11_layouts_from_files()


def verify_x11_keyboard_layout(layout: str) -> bool:
	for language in list_x11_keyboard_languages():
		if layout.lower() == language.lower():
			return True
	return False


def get_kb_layout() -> str:
	# Try localectl first (systemd)
	if shutil.which('localectl'):
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

	# Fallback: try reading /etc/vconsole.conf or similar
	vconsole = Path('/etc/vconsole.conf')
	if vconsole.exists():
		for line in vconsole.read_text().splitlines():
			if line.startswith('KEYMAP='):
				layout = line.split('=', 1)[1].strip().strip('"\'')
				if verify_keyboard_layout(layout):
					return layout

	return ''


def set_kb_layout(locale: str) -> bool:
	if running_from_host():
		# Skip when running from host - no need to change host keymap
		# The target installation keymap is set via installer.set_vconsole()
		return True

	if len(locale.strip()):
		if not verify_keyboard_layout(locale):
			error(f'Invalid keyboard locale specified: {locale}')
			return False

		# Try localectl first (systemd)
		if shutil.which('localectl'):
			try:
				SysCommand(f'localectl set-keymap {locale}')
			except SysCallError as err:
				raise ServiceException(f"Unable to set locale '{locale}' for console: {err}")
		else:
			# Fallback: use loadkeys directly
			if shutil.which('loadkeys'):
				try:
					SysCommand(f'loadkeys {locale}')
				except SysCallError as err:
					raise ServiceException(f"Unable to set locale '{locale}' for console: {err}")

		return True

	return False


def list_timezones() -> list[str]:
	# Try timedatectl first (systemd)
	if shutil.which('timedatectl'):
		return (
			SysCommand(
				'timedatectl --no-pager list-timezones',
				environment_vars={'SYSTEMD_COLORS': '0'},
			)
			.decode()
			.splitlines()
		)

	# Fallback: read from zoneinfo directory (works on Alpine, etc.)
	zoneinfo = Path('/usr/share/zoneinfo')
	if not zoneinfo.exists():
		return []

	timezones = []
	# Skip these directories as they're not actual timezones
	skip = {'posix', 'right', 'posixrules', 'localtime', 'leap-seconds.list', 'leapseconds', 'tzdata.zi', 'zone.tab', 'zone1970.tab', 'iso3166.tab'}

	for path in sorted(zoneinfo.rglob('*')):
		if path.is_file() and not any(part in skip for part in path.parts):
			tz = str(path.relative_to(zoneinfo))
			# Filter to only include common timezone formats (e.g., America/New_York)
			if '/' in tz and not tz.startswith('+'):
				timezones.append(tz)

	return timezones
