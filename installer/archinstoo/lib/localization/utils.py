import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import RequirementError, ServiceException, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.output import error
from archinstoo.lib.utils.env import Os
from archinstoo.lib.utils.net import fetch_data_from_url

if TYPE_CHECKING:
	from collections.abc import Iterable


def list_keyboard_languages() -> list[str]:
	try:
		out = SysCommand(
			'localectl --no-pager list-keymaps',
			environment_vars={'SYSTEMD_COLORS': '0'},
		).decode()
		if out.strip():
			return out.splitlines()
	except SysCallError, RequirementError:
		# SysCallError: localectl present but failed. RequirementError: no
		# localectl at all (non-systemd host). Either way scan kbd data.
		pass

	# localectl reads compiled-in FHS keymap dirs that don't exist on e.g.
	# NixOS; scan local kbd data, then fall back to the upstream kbd tree when
	# the host ships no kbd keymaps at all (alpine, foreign hosts)
	return _scan_keymaps() or _fetch_kbd_keymaps()


def _scan_keymaps() -> list[str]:
	# kbd keymap files (*.map[.gz]) live under different roots per distro;
	# locate via the loadkeys binary's prefix, plus the common FHS spots.
	roots = [Path('/usr/share/kbd/keymaps'), Path('/usr/share/keymaps')]
	if loadkeys := shutil.which('loadkeys'):
		prefix = Path(loadkeys).resolve().parent.parent
		roots += [prefix / 'share/kbd/keymaps', prefix / 'share/keymaps']

	names = {p.name.removesuffix('.gz').removesuffix('.map') for root in roots if root.is_dir() for p in root.rglob('*.map*')}
	return sorted(names)


# upstream kbd mirror; its data/ tree is the canonical source of kbd keymap and
# console-font names, used when the host carries none (e.g. alpine/musl)
_KBD_TREE_URL = 'https://api.github.com/repos/legionus/kbd/git/trees/master?recursive=1'
# base.lst is generated at build time so the source ships only base.xml; the raw
_X11_BASE_XML_URL = 'https://gitlab.freedesktop.org/xkeyboard-config/xkeyboard-config/-/raw/master/rules/base.xml?ref_type=heads'


def _fetch_kbd_tree_names(prefix: str) -> list[str]:
	# return the basename of every file under <prefix> in the kbd git tree
	try:
		tree = json.loads(fetch_data_from_url(_KBD_TREE_URL)).get('tree', [])
	except ValueError:
		return []

	return [entry['path'].rsplit('/', 1)[-1] for entry in tree if entry.get('type') == 'blob' and entry.get('path', '').startswith(prefix)]


def _fetch_kbd_keymaps() -> list[str]:
	# keymap name is the filename minus the .map[.gz] suffix (matches loadkeys)
	names = set()
	for fn in _fetch_kbd_tree_names('data/keymaps/'):
		if fn.endswith('.map.gz'):
			names.add(fn[:-7])
		elif fn.endswith('.map'):
			names.add(fn[:-4])

	return sorted(names)


# glibc lists every locale it can generate here; fetched only on non-glibc hosts
_GLIBC_SUPPORTED_URL = 'https://raw.githubusercontent.com/bminor/glibc/master/localedata/SUPPORTED'

# host copy of the same list, shipped by glibc
_SUPPORTED_PATH = Path('/usr/share/i18n/SUPPORTED')

# glibc >= 2.35 compiles these in, so Arch's /etc/locale.gen omits them even
# though SUPPORTED lists them. Offering one means Installer.set_locale finds no
# matching locale.gen entry and the install ends with no locale.conf.
_BUILTIN_LOCALES = frozenset({'C.UTF-8 UTF-8'})

# last-resort set if disk and network both fail, so the menu is never empty
_MIN_LOCALES = ['en_US.UTF-8 UTF-8']


def _generatable(locales: Iterable[str]) -> list[str]:
	# every list_locales source runs through here: menu entries must map 1:1
	# onto commented /etc/locale.gen lines on the target
	return [locale for locale in locales if locale and locale not in _BUILTIN_LOCALES]


def _fetch_glibc_supported() -> list[str]:
	# upstream lists each locale as "<locale>/<charset> \"; convert to the
	# space-separated "<locale> <charset>" form the menu expects
	try:
		text = fetch_data_from_url(_GLIBC_SUPPORTED_URL)
	except ValueError:
		return []

	locales = []
	for raw in text.splitlines():
		line = raw.strip().rstrip('\\').strip()
		if not line or line.startswith(('#', 'SUPPORTED-LOCALES')) or '/' not in line:
			continue
		locale, charset = line.rsplit('/', 1)
		locales.append(f'{locale} {charset}')

	return _generatable(locales)


def list_locales() -> list[str]:
	# glibc hosts enumerate from i18n/SUPPORTED
	if _SUPPORTED_PATH.is_file():
		with _SUPPORTED_PATH.open() as file:
			return _generatable(line.rstrip() for line in file)

	# non-glibc host (musl/alpine): no SUPPORTED on disk, pull the canonical
	# list glibc ships upstream so the target (Arch/glibc) choices are accurate
	return _fetch_glibc_supported() or _MIN_LOCALES


def split_locale_name(sys_lang: str) -> tuple[str, str, str]:
	# 'be_BY.UTF-8@latin' -> ('be_BY', 'UTF-8', '@latin'). The codeset comes
	# back empty for names that omit it ('en_IL'). Peel the modifier first: it
	# always trails the codeset, never the reverse (setlocale(3)).
	name, modifier = sys_lang, ''
	if '@' in name:
		name, mod = name.split('@', 1)
		modifier = f'@{mod}'

	lang, _, codeset = name.partition('.')
	return lang, codeset, modifier


def locale_encoding(sys_lang: str, sys_enc: str) -> str:
	# a name spelling its own codeset ('en_GB.UTF-8') outranks the UTF-8 the
	# encoding menu carries by default
	codeset = split_locale_name(sys_lang)[1]
	return codeset if codeset and sys_enc == 'UTF-8' else sys_enc


def locale_entry_re(sys_lang: str, sys_enc: str) -> re.Pattern[str]:
	# matches the SUPPORTED/locale.gen entry a selection needs. The first
	# column names the codeset only sometimes ('en_IL UTF-8' vs 'en_GB.UTF-8
	# UTF-8'), so both spellings match; anchor with fullmatch, else the
	# ISO-8859-1 pattern also swallows 'xx_XX ISO-8859-15'.
	lang, _, modifier = split_locale_name(sys_lang)
	enc = locale_encoding(sys_lang, sys_enc)
	return re.compile(rf'{re.escape(lang)}(\.{re.escape(enc)})?{re.escape(modifier)} {re.escape(enc)}')


def list_locale_encodings(sys_lang: str) -> list[str]:
	# encodings are language-scoped the way xkb variants are layout-scoped:
	# only ~870 of the ~15000 language x encoding pairs name a real locale, and
	# a pair that names none leaves the install with no locale.conf at all.
	# UTF-8 leads so a language switch lands on it when it is available.
	if codeset := split_locale_name(sys_lang)[1]:
		# the name already fixed the codeset; pairing it with another charset
		# installs that charset under a name claiming this one
		return [codeset]

	entries = [entry.strip() for entry in list_locales()]
	charsets = {entry.split()[1] for entry in entries}
	scoped = [enc for enc in charsets if any(locale_entry_re(sys_lang, enc).fullmatch(entry) for entry in entries)]
	return sorted(scoped, key=lambda enc: (enc != 'UTF-8', enc))


def verify_keyboard_layout(layout: str) -> bool:
	return any(layout.lower() == language.lower() for language in list_keyboard_languages())


def _localectl_keymap(subcmd: str) -> list[str]:
	# raises SysCallError/RequirementError when localectl is absent or fails
	return (
		SysCommand(
			f'localectl --no-pager {subcmd}',
			environment_vars={'SYSTEMD_COLORS': '0'},
		)
		.decode()
		.splitlines()
	)


def _fetch_x11_registry() -> ET.Element | None:
	# upstream xkeyboard-config rules registry; used when localectl is missing
	# (non-systemd hosts: alpine, foreign hosts, ...)
	try:
		text = fetch_data_from_url(_X11_BASE_XML_URL)
	except ValueError:
		return None
	try:
		return ET.fromstring(text)  # noqa: S314 - trusted xkeyboard-config source over https
	except ET.ParseError:
		return None


def _fetch_x11_names(xpath: str) -> list[str]:
	root = _fetch_x11_registry()
	if root is None:
		return []
	return [name.text for name in root.findall(xpath) if name.text]


def list_x11_keyboard_languages() -> list[str]:
	try:
		if out := _localectl_keymap('list-x11-keymap-layouts'):
			return out
	except SysCallError, RequirementError:
		# no localectl (non-systemd host) or it failed; fetch from upstream
		pass
	return _fetch_x11_names('./layoutList/layout/configItem/name')


def list_x11_keyboard_models() -> list[str]:
	try:
		if out := _localectl_keymap('list-x11-keymap-models'):
			return out
	except SysCallError, RequirementError:
		pass
	return _fetch_x11_names('./modelList/model/configItem/name')


def list_x11_keyboard_options() -> list[str]:
	try:
		if out := _localectl_keymap('list-x11-keymap-options'):
			return out
	except SysCallError, RequirementError:
		pass
	return _fetch_x11_names('./optionList/group/option/configItem/name')


def list_x11_keyboard_variants(layout: str) -> list[str]:
	# variants are layout-scoped (e.g. 'be' -> nodeadkeys, oss, ...)
	if not layout.strip():
		return []
	try:
		if out := _localectl_keymap(f'list-x11-keymap-variants {layout}'):
			return out
	except SysCallError, RequirementError:
		pass
	return _fetch_x11_variants(layout)


def _fetch_x11_variants(layout: str) -> list[str]:
	# variant names live under the matching layout's variantList in the registry
	root = _fetch_x11_registry()
	if root is None:
		return []
	for lay in root.findall('./layoutList/layout'):
		name_el = lay.find('./configItem/name')
		if name_el is not None and name_el.text == layout:
			return [n.text for n in lay.findall('./variantList/variant/configItem/name') if n.text]
	return []


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

	if not vcline:
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
			raise ServiceException(f"Unable to set locale '{locale}' for console: {err}") from err

		return True

	return False


# disk fonts are gz-compressed (.psfu.gz); the upstream repo ships them raw
_FONT_SUFFIXES = ('.psfu.gz', '.psf.gz', '.gz', '.psfu', '.psf')


def _strip_font_suffix(name: str) -> str:
	for suffix in _FONT_SUFFIXES:
		if name.endswith(suffix):
			return name[: -len(suffix)]
	return name


def list_console_fonts() -> list[str]:
	font_dir = Path('/usr/share/kbd/consolefonts')

	if font_dir.exists():
		# skip documentation files (README*)
		fonts = [_strip_font_suffix(f.name) for f in font_dir.iterdir() if not f.name.startswith('README')]
		if fonts:
			return sorted(fonts, key=lambda x: (len(x), x))

	# foreign host with no kbd consolefonts on disk (alpine): names from upstream
	return _fetch_kbd_fonts()


def _fetch_kbd_fonts() -> list[str]:
	fonts = [_strip_font_suffix(fn) for fn in _fetch_kbd_tree_names('data/consolefonts/') if not fn.startswith('README')]
	return sorted(fonts, key=lambda x: (len(x), x))


def list_timezones() -> list[str]:
	try:
		out = SysCommand(
			'timedatectl --no-pager list-timezones',
			environment_vars={'SYSTEMD_COLORS': '0'},
		).decode()
		if out.strip():
			return out.splitlines()
	except SysCallError, RequirementError:
		# RequirementError: no timedatectl (non-systemd host). SysCallError:
		# present but failed. Read the tz db off disk in both cases.
		pass

	# timedatectl talks to systemd-timedated over dbus; on a host with no
	# running timedated the call blocks until the dbus activation timeout
	# (looks hung). Read the tz db off disk instead.
	return _scan_timezones()


def _scan_timezones() -> list[str]:
	# zone1970.tab / zone.tab list the canonical zone names in their last
	# tab-separated column (lines starting with # are comments). Honor glibc's
	# TZDIR so non-FHS hosts (NixOS) can point at the tzdata store path.
	root = Path(os.environ.get('TZDIR') or '/usr/share/zoneinfo')
	for tab in ('zone1970.tab', 'zone.tab'):
		tabfile = root / tab
		if not tabfile.is_file():
			continue
		zones = {cols[2] for line in tabfile.read_text().splitlines() if not line.startswith('#') and len(cols := line.split('\t')) >= 3}
		if zones:
			zones.add('UTC')
			return sorted(zones)
	return []
