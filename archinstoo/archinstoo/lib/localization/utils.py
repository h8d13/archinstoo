import shutil
from pathlib import Path

from archinstoo.lib.exceptions import ServiceException, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.output import error
from archinstoo.lib.utils.env import Os


def list_keyboard_languages() -> list[str]:
	try:
		out = SysCommand(
			'localectl --no-pager list-keymaps',
			environment_vars={'SYSTEMD_COLORS': '0'},
		).decode()
		if out.strip():
			return out.splitlines()
	except SysCallError:
		pass

	# localectl reads compiled-in FHS keymap dirs that don't exist on e.g.
	# NixOS; fall back to scanning the kbd data directly.
	return _scan_keymaps()


def _scan_keymaps() -> list[str]:
	# kbd keymap files (*.map[.gz]) live under different roots per distro;
	# locate via the loadkeys binary's prefix, plus the common FHS spots.
	roots = [Path('/usr/share/kbd/keymaps'), Path('/usr/share/keymaps')]
	if loadkeys := shutil.which('loadkeys'):
		prefix = Path(loadkeys).resolve().parent.parent
		roots += [prefix / 'share/kbd/keymaps', prefix / 'share/keymaps']

	names = {p.name.removesuffix('.gz').removesuffix('.map') for root in roots if root.is_dir() for p in root.rglob('*.map*')}
	return sorted(names)


def list_locales() -> list[str]:
	with Path('/usr/share/i18n/SUPPORTED').open() as file:
		return [line.rstrip() for line in file if line != 'C.UTF-8 UTF-8\n']


def verify_keyboard_layout(layout: str) -> bool:
	return any(layout.lower() == language.lower() for language in list_keyboard_languages())


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
	return any(layout.lower() == language.lower() for language in list_x11_keyboard_languages())


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
	try:
		out = SysCommand(
			'timedatectl --no-pager list-timezones',
			environment_vars={'SYSTEMD_COLORS': '0'},
		).decode()
		if out.strip():
			return out.splitlines()
	except SysCallError:
		pass

	# timedatectl talks to systemd-timedated over dbus; on a host with no
	# running timedated the call blocks until the dbus activation timeout
	# (looks hung). Read the tz db off disk instead.
	return _scan_timezones()


def _scan_timezones() -> list[str]:
	# zone1970.tab / zone.tab list the canonical zone names in their last
	# tab-separated column (lines starting with # are comments).
	root = Path('/usr/share/zoneinfo')
	for tab in ('zone1970.tab', 'zone.tab'):
		tabfile = root / tab
		if not tabfile.is_file():
			continue
		zones = {cols[2] for line in tabfile.read_text().splitlines() if not line.startswith('#') and len(cols := line.split('\t')) >= 3}
		if zones:
			zones.add('UTC')
			return sorted(zones)
	return []
