import shutil
from pathlib import Path

from archinstoo.lib.exceptions import ServiceException, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.output import error
from archinstoo.lib.utils.env import Os


def _list_keymaps_from_kbd_git() -> list[str]:
	"""Fetch console keymap names from the upstream kbd git tree."""
	import json
	import urllib.request

	url = 'https://api.github.com/repos/legionus/kbd/git/trees/master?recursive=1'
	req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json'})
	with urllib.request.urlopen(req, timeout=10) as resp:
		tree = json.loads(resp.read().decode('utf-8'))

	keymaps: list[str] = []
	for entry in tree.get('tree', []):
		if entry.get('type') != 'blob':
			continue
		path = entry['path']
		if not path.startswith('data/keymaps/'):
			continue
		name = Path(path).name
		if name.endswith('.map.gz'):
			keymaps.append(name[: -len('.map.gz')])
		elif name.endswith('.map'):
			keymaps.append(name[: -len('.map')])

	return sorted(set(keymaps))


def list_keyboard_languages() -> list[str]:
	if shutil.which('localectl'):
		return SysCommand('localectl --no-pager list-keymaps', environment_vars={'SYSTEMD_COLORS': '0'}).decode().splitlines()
	try:
		return _list_keymaps_from_kbd_git()
	except Exception:
		return []


def verify_keyboard_layout(layout: str) -> bool:
	return any(layout.lower() == language.lower() for language in list_keyboard_languages())


def _list_x11_layouts_from_xkb_git() -> list[str]:
	"""Fetch X11 layout names from upstream xkeyboard-config."""
	import urllib.request

	url = 'https://gitlab.freedesktop.org/xkeyboard-config/xkeyboard-config/-/raw/master/rules/base.lst'
	with urllib.request.urlopen(url, timeout=10) as resp:
		text = resp.read().decode('utf-8')

	layouts: list[str] = []
	in_layout_section = False
	for line in text.splitlines():
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
	try:
		return _list_x11_layouts_from_xkb_git()
	except Exception:
		return []


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
	try:
		import json
		import urllib.request

		url = 'https://api.github.com/repos/legionus/kbd/git/trees/master?recursive=1'
		req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json'})
		with urllib.request.urlopen(req, timeout=10) as resp:
			tree = json.loads(resp.read().decode('utf-8'))

		fonts: list[str] = []
		for entry in tree.get('tree', []):
			if entry.get('type') != 'blob':
				continue
			path = entry['path']
			if not path.startswith('data/consolefonts/'):
				continue
			name = Path(path).name
			if name.startswith('README'):
				continue
			for suffix in ('.psfu.gz', '.psf.gz', '.gz', '.psfu', '.psf'):
				if name.endswith(suffix):
					name = name[: -len(suffix)]
					break
			fonts.append(name)

		return sorted(set(fonts), key=lambda x: (len(x), x))
	except Exception:
		return []


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
