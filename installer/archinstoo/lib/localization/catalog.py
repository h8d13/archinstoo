import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import RequirementError, ServiceError, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.output import debug, error, warn
from archinstoo.lib.utils.env import Os
from archinstoo.lib.utils.net import fetch_data_from_url

if TYPE_CHECKING:
	from collections.abc import Iterable


def list_keyboard_languages() -> list[str]:
	# the kbd keymaps on disk, which is what localectl would fork to read back
	# (same 252 names on Arch) off dirs it has compiled in and that a NixOS or
	# alpine host does not have. Upstream kbd tree when the host ships none
	if names := _scan_keymaps():
		return names
	debug('No local kbd keymaps, fetching the upstream kbd tree')
	return _fetch_kbd_keymaps()


def share_paths(anchor: str, *relative: str) -> list[Path]:
	# Data a package ships next to its binaries: /usr/share on an FHS host,
	# <prefix>/share on a store based one (NixOS keeps no /usr/share at all,
	# but every binary resolves into its own package). Callers get the
	# candidates in preference order and pick the ones that exist.
	roots = [Path('/usr')]
	if binary := shutil.which(anchor):
		roots.append(Path(binary).resolve().parent.parent)

	return [root / 'share' / rel for root in roots for rel in relative]


def _scan_keymaps() -> list[str]:
	# kbd keymap files (*.map[.gz]) live under different roots per distro
	roots = share_paths('loadkeys', 'kbd/keymaps', 'keymaps')
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
	except ValueError as e:
		debug(f'Fetch failed for {_KBD_TREE_URL}: {e}')
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
	except ValueError as e:
		debug(f'Fetch failed for {_GLIBC_SUPPORTED_URL}: {e}')
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
	if locales := _fetch_glibc_supported():
		return locales
	warn('Could not fetch the glibc locale list, offering en_US.UTF-8 only')
	return _MIN_LOCALES


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


def uncomment_locale(lines: list[str], sys_lang: str, sys_enc: str) -> bool:
	entry_re = locale_entry_re(sys_lang, sys_enc)
	for index, line in enumerate(lines):
		if entry_re.fullmatch(line.removeprefix('#').strip()):
			lines[index] = line.removeprefix('#')
			return True
	return False


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


# xkeyboard-config's registry is what localectl serves its X11 lists from, so
# read it here instead of forking per list. evdev is the ruleset Linux uses,
# base its pre-evdev name; hosts ship one, the other, or both as copies
_X11_RULES = ('X11/xkb/rules/evdev.xml', 'X11/xkb/rules/base.xml')


@cache
def _load_x11_registry() -> ET.Element:
	# cached: the variant list is re-read on every layout change in the menu,
	# and the registry is a quarter of a megabyte of XML. Raises instead of
	# returning None when there is nothing to read: cache stores returns, not
	# exceptions, so a blip on the fetch path is retried by the next caller
	# rather than emptying every keymap list for the rest of the run
	for path in share_paths('setxkbmap', *_X11_RULES):
		if not path.is_file():
			continue
		try:
			return ET.parse(path).getroot()  # noqa: S314 - distro-shipped xkeyboard-config data
		except ET.ParseError as e:
			warn(f'Could not parse {path}: {e}')

	# host ships no xkeyboard-config (alpine, minimal foreign hosts)
	debug('No local xkeyboard-config registry, fetching the upstream one')
	if (root := _fetch_x11_registry()) is None:
		raise RequirementError('no xkeyboard-config registry on disk or upstream')
	return root


def _x11_registry() -> ET.Element | None:
	try:
		return _load_x11_registry()
	except RequirementError as e:
		debug(f'X11 keymap lists unavailable: {e}')
		return None


def _fetch_x11_registry() -> ET.Element | None:
	# upstream xkeyboard-config rules registry, for hosts carrying none
	try:
		text = fetch_data_from_url(_X11_BASE_XML_URL)
	except ValueError as e:
		warn(f'Could not fetch the xkeyboard-config registry: {e}')
		return None
	try:
		return ET.fromstring(text)  # noqa: S314 - trusted xkeyboard-config source over https
	except ET.ParseError as e:
		warn(f'Could not parse the xkeyboard-config registry: {e}')
		return None


def _x11_names(xpath: str) -> list[str]:
	root = _x11_registry()
	if root is None:
		return []
	return [name.text for name in root.findall(xpath) if name.text]


def list_x11_keyboard_languages() -> list[str]:
	return _x11_names('./layoutList/layout/configItem/name')


def list_x11_keyboard_models() -> list[str]:
	return _x11_names('./modelList/model/configItem/name')


def list_x11_keyboard_options() -> list[str]:
	# leaf options only: the group names localectl also prints (caps, grp, ...)
	# are headings, not values XkbOptions accepts
	return _x11_names('./optionList/group/option/configItem/name')


def list_x11_keyboard_variants(layout: str) -> list[str]:
	# variants are layout-scoped (e.g. 'be' -> nodeadkeys, oss, ...)
	if not layout.strip():
		return []

	root = _x11_registry()
	if root is None:
		return []
	for lay in root.findall('./layoutList/layout'):
		name_el = lay.find('./configItem/name')
		if name_el is not None and name_el.text == layout:
			return [n.text for n in lay.findall('./variantList/variant/configItem/name') if n.text]
	return []


# systemd's console keymap -> X11 layout table, the one `localectl set-keymap`
# applies when it converts. Shipped by systemd itself, so it is there whenever
# the host can run localectl at all
_KBD_MODEL_MAP = 'systemd/kbd-model-map'


def _kbd_model_map_path() -> Path | None:
	# systemd ships it, so localectl anchors the store based case
	return next((p for p in share_paths('localectl', _KBD_MODEL_MAP) if p.is_file()), None)


@cache
def _kbd_model_map() -> dict[str, tuple[str, str]]:
	# console keymap -> (layout, variant), first row wins the way localed reads
	# it. Model and options columns are dropped on purpose: the model column
	# carries 'pc105+inet', which xkeyboard-config does not list, and every row
	# sets terminate:ctrl_alt_bksp, a policy Arch does not ship
	table: dict[str, tuple[str, str]] = {}
	path = _kbd_model_map_path()
	if path is None:
		debug('No kbd-model-map on this host, graphical layout stays unset until chosen')
		return table

	for line in path.read_text().splitlines():
		if line.startswith('#') or len(cols := line.split()) < 4:
			continue
		keymap, layout, _model, variant = cols[:4]
		# 'ru,us' and friends are two-group setups that only work with the
		# grp: toggle on the same row; a single layout field cannot hold one
		if ',' in layout or keymap in table:
			continue
		table[keymap] = (layout, '' if variant == '-' else variant)

	return table


def xkb_from_keymap(keymap: str) -> tuple[str, str] | None:
	# (layout, variant) for a console keymap, None when the table has no
	# single-layout row for it. Every layout it can return is in the
	# xkeyboard-config registry, so callers need no second check
	return _kbd_model_map().get(keymap)


def verify_x11_keyboard_layout(layout: str) -> bool:
	return any(layout.lower() == language.lower() for language in list_x11_keyboard_languages())


@cache
def get_kb_layout() -> str:
	# cached: LocaleConfiguration.default() calls this, and the locale menu
	# builds a default per preview redraw, so an uncached probe forks
	# localectl on every keystroke (and on a host without one, logs the same
	# failure that many times). set_kb_layout() clears it when it moves
	try:
		lines = (
			SysCommand(
				'localectl --no-pager status',
				environment_vars={'SYSTEMD_COLORS': '0'},
			)
			.decode()
			.splitlines()
		)
	except Exception as e:
		debug(f'localectl status failed, no host keymap detected: {e}')
		return ''

	vcline = ''
	for line in lines:
		if 'VC Keymap: ' in line:
			vcline = line

	if not vcline:
		return ''

	layout = vcline.split(': ')[1]
	if not verify_keyboard_layout(layout):
		debug(f'Host keymap {layout} not in the keymap list, ignoring')
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
			raise ServiceError(f"Unable to set locale '{locale}' for console: {err}") from err

		# the host keymap just moved, so the cached probe above is stale
		get_kb_layout.cache_clear()
		return True

	return False


_FONT_DIRS = ('kbd/consolefonts', 'consolefonts')

# disk fonts are gz-compressed (.psfu.gz); the upstream repo ships them raw
_FONT_SUFFIXES = ('.psfu.gz', '.psf.gz', '.gz', '.psfu', '.psf')

_FONT_EXTS = ('.psfu', '.psf', '.cp', '.fnt')
_FONT_COMPRESSION = ('.gz', '.bz2', '.zst')


def _strip_font_suffix(name: str) -> str:
	for suffix in _FONT_SUFFIXES:
		if name.endswith(suffix):
			return name[: -len(suffix)]
	return name


def _is_font_name(name: str) -> bool:
	# what the sd-vconsole/consolefont hooks glob for, so the menu cannot offer
	# a FONT= they reject. Forty kbd fonts carry no extension at all (alt-8x16,
	# koi8r-8x16, ...), hence compression alone qualifying.
	return name.endswith(_FONT_COMPRESSION) or name.endswith(_FONT_EXTS)


def list_console_fonts() -> list[str]:
	for font_dir in share_paths('setfont', *_FONT_DIRS):
		if not font_dir.is_dir():
			continue
		# README.psfu passes _is_font_name, so the prefix check still earns its keep
		fonts = [_strip_font_suffix(f.name) for f in font_dir.iterdir() if f.is_file() and not f.name.startswith('README') and _is_font_name(f.name)]
		if fonts:
			return sorted(fonts, key=lambda x: (len(x), x))

	# foreign host with no kbd consolefonts on disk (alpine): names from upstream
	return _fetch_kbd_fonts()


def _fetch_kbd_fonts() -> list[str]:
	names = _fetch_kbd_tree_names('data/consolefonts/')
	fonts = [_strip_font_suffix(fn) for fn in names if not fn.startswith('README') and _is_font_name(fn)]
	return sorted(fonts, key=lambda x: (len(x), x))


def list_timezones() -> list[str]:
	try:
		out = SysCommand(
			'timedatectl --no-pager list-timezones',
			environment_vars={'SYSTEMD_COLORS': '0'},
		).decode()
		if out.strip():
			return out.splitlines()
	except (SysCallError, RequirementError) as e:
		# RequirementError: no timedatectl (non-systemd host). SysCallError:
		# present but failed. Read the tz db off disk in both cases.
		debug(f'timedatectl unavailable ({e}), reading the tz db off disk')

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
