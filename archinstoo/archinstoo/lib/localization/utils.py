import shutil
from pathlib import Path

from archinstoo.lib.exceptions import ServiceException, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.output import error
from archinstoo.lib.utils.env import Os


def _list_keymaps_from_files() -> list[str]:
	"""Fallback: enumerate console keymaps directly from kbd/keymaps files."""
	keymaps: list[str] = []

	for kbd_path in (Path('/usr/share/kbd/keymaps'), Path('/usr/share/keymaps')):
		if not kbd_path.exists():
			continue
		keymaps.extend(path.stem.replace('.map', '') for path in kbd_path.rglob('*.map.gz'))
		keymaps.extend(path.stem for path in kbd_path.rglob('*.map'))
		break  # use the first directory that exists

	return sorted(set(keymaps))


def list_keyboard_languages() -> list[str]:
	if shutil.which('localectl'):
		return SysCommand('localectl --no-pager list-keymaps', environment_vars={'SYSTEMD_COLORS': '0'}).decode().splitlines()
	return _list_keymaps_from_files()


def verify_keyboard_layout(layout: str) -> bool:
	return any(layout.lower() == language.lower() for language in list_keyboard_languages())


def _list_x11_layouts_from_files() -> list[str]:
	"""Fallback: parse X11 layout names from xkb rules files."""
	layouts: list[str] = []

	for rules_path in (
		Path('/usr/share/X11/xkb/rules/base.lst'),
		Path('/usr/share/X11/xkb/rules/evdev.lst'),
	):
		if not rules_path.exists():
			continue
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
	if shutil.which('localectl'):
		return (
			SysCommand(
				'localectl --no-pager list-x11-keymap-layouts',
				environment_vars={'SYSTEMD_COLORS': '0'},
			)
			.decode()
			.splitlines()
		)
	return _list_x11_layouts_from_files()


def verify_x11_keyboard_layout(layout: str) -> bool:
	return any(layout.lower() == language.lower() for language in list_x11_keyboard_languages())


def get_kb_layout() -> str:
	if shutil.which('localectl'):
		try:
			lines = SysCommand('localectl --no-pager status', environment_vars={'SYSTEMD_COLORS': '0'}).decode().splitlines()
		except Exception:
			return ''

		for line in lines:
			if 'VC Keymap: ' in line:
				layout = line.split(': ', 1)[1].strip()
				return layout if verify_keyboard_layout(layout) else ''
		return ''

	# Fallback: read /etc/vconsole.conf (written by systemd or by us)
	vconsole = Path('/etc/vconsole.conf')
	if vconsole.exists():
		for line in vconsole.read_text().splitlines():
			if line.startswith('KEYMAP='):
				layout = line.split('=', 1)[1].strip().strip('"\'')
				return layout if verify_keyboard_layout(layout) else ''

	return ''


def set_kb_layout(locale: str) -> bool:
	if Os.running_from_host():
		# The target installation keymap is set via installer.set_vconsole()
		return True

	if not locale.strip():
		return False

	if not verify_keyboard_layout(locale):
		error(f'Invalid keyboard locale specified: {locale}')
		return False

	if shutil.which('localectl'):
		try:
			SysCommand(f'localectl set-keymap {locale}')
		except SysCallError as err:
			raise ServiceException(f"Unable to set locale '{locale}' for console: {err}")
	elif shutil.which('loadkeys'):
		try:
			SysCommand(f'loadkeys {locale}')
		except SysCallError as err:
			raise ServiceException(f"Unable to set locale '{locale}' for console: {err}")

	return True


def list_console_fonts() -> list[str]:
	font_dir = Path('/usr/share/kbd/consolefonts')
	fonts: list[str] = []

	if font_dir.exists():
		for f in font_dir.iterdir():
			if f.name.startswith('README'):
				continue
			name = f.name
			for suffix in ('.psfu.gz', '.psf.gz', '.gz'):
				if name.endswith(suffix):
					name = name[: -len(suffix)]
					break
			fonts.append(name)

	return sorted(fonts, key=lambda x: (len(x), x))


def _valid_locale(line: str) -> bool:
	parts = line.split()
	return len(parts) >= 2 and parts[0] != 'C.UTF-8'


def list_locales() -> list[str]:
	supported = Path('/usr/share/i18n/SUPPORTED')
	if supported.exists():
		return [line.rstrip() for line in supported.read_text().splitlines() if _valid_locale(line)]

	# Fallback: uncommented entries in /etc/locale.gen
	locale_gen = Path('/etc/locale.gen')
	if locale_gen.exists():
		locales = [line.strip() for line in locale_gen.read_text().splitlines() if _valid_locale(line.strip())]
		if locales:
			return locales

	# Last resort: fetch upstream glibc SUPPORTED list
	# Source format: "en_US.UTF-8/UTF-8 \" — convert to "en_US.UTF-8 UTF-8"
	try:
		import urllib.request

		url = 'https://raw.githubusercontent.com/bminor/glibc/master/localedata/SUPPORTED'
		with urllib.request.urlopen(url, timeout=5) as resp:
			text = resp.read().decode('utf-8')
		locales = []
		for line in text.splitlines():
			line = line.rstrip(' \\').strip()
			if not line or line.startswith('#'):
				continue
			entry = line.replace('/', ' ', 1)
			if _valid_locale(entry):
				locales.append(entry)
		return locales
	except Exception:
		pass

	return []


def list_timezones() -> list[str]:
	if shutil.which('timedatectl'):
		return SysCommand('timedatectl --no-pager list-timezones', environment_vars={'SYSTEMD_COLORS': '0'}).decode().splitlines()

	# Fallback: scan /usr/share/zoneinfo directly (works on Alpine and any distro)
	zoneinfo = Path('/usr/share/zoneinfo')
	if not zoneinfo.exists():
		return []

	_skip = {
		'posix',
		'right',
		'posixrules',
		'localtime',
		'leap-seconds.list',
		'leapseconds',
		'tzdata.zi',
		'zone.tab',
		'zone1970.tab',
		'iso3166.tab',
	}

	timezones: list[str] = []
	for path in sorted(zoneinfo.rglob('*')):
		if not path.is_file():
			continue
		if any(part in _skip for part in path.parts):
			continue
		tz = str(path.relative_to(zoneinfo))
		if '/' in tz and not tz.startswith('+'):
			timezones.append(tz)

	return timezones
