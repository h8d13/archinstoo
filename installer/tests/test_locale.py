# glibc's SUPPORTED lists UTF-8-only locales without a ".UTF-8" suffix in the
# first column (no other charset variant exists to disambiguate from). Written
# bare to locale.conf, tools sniffing LANG for "UTF-8" (tmux et al.) drop to
# legacy charsets. set_locale writes the fully qualified name to locale.conf;
# it resolves against the bare compiled locale because localedef registers a
# normalized-codeset alias for codeset-less names (glibc locarchive.c).
# All entries below are verbatim from /usr/share/i18n/SUPPORTED.

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import pytest

from archinstoo.lib.installer import Installer
from archinstoo.lib.localization import catalog
from archinstoo.lib.menu import locale_menu
from archinstoo.lib.models.locale import LocaleConfiguration

if TYPE_CHECKING:
	from collections.abc import Iterator
	from pathlib import Path


# Arch's generated /etc/locale.gen keeps the trailing spaces from SUPPORTED.
# ca_AD carries ISO-8859-15 and no ISO-8859-1; de_DE@euro is one of the 22
# languages that exist under no UTF-8 entry at all.
_LOCALE_GEN = (
	'#be_BY.UTF-8 UTF-8  \n'
	'#be_BY CP1251  \n'
	'#be_BY@latin UTF-8  \n'
	'#ca_AD.UTF-8 UTF-8  \n'
	'#ca_AD ISO-8859-15  \n'
	'#de_DE.UTF-8 UTF-8  \n'
	'#de_DE ISO-8859-1  \n'
	'#de_DE@euro ISO-8859-15  \n'
	'#en_GB.UTF-8 UTF-8  \n'
	'#en_GB ISO-8859-1  \n'
	'#en_IL UTF-8  \n'
	'#en_US.UTF-8 UTF-8  \n'
	'#en_US ISO-8859-1  \n'
)


# /usr/share/i18n/SUPPORTED as glibc ships it: the same entries uncommented and
# without trailing spaces, plus the compiled-in C.UTF-8 locale.gen never carries
_DISK_SUPPORTED = (
	'C.UTF-8 UTF-8\n'
	'be_BY.UTF-8 UTF-8\n'
	'be_BY CP1251\n'
	'be_BY@latin UTF-8\n'
	'ca_AD.UTF-8 UTF-8\n'
	'ca_AD ISO-8859-15\n'
	'de_DE.UTF-8 UTF-8\n'
	'de_DE ISO-8859-1\n'
	'de_DE@euro ISO-8859-15\n'
	'en_GB.UTF-8 UTF-8\n'
	'en_GB ISO-8859-1\n'
	'en_IL UTF-8\n'
	'en_US.UTF-8 UTF-8\n'
	'en_US ISO-8859-1\n'
)

# upstream glibc localedata/SUPPORTED: "<locale>/<charset> \" under a header
_GLIBC_SUPPORTED = (
	'# This file names the currently supported and somewhat tested locales.\n'
	'SUPPORTED-LOCALES=\\\n'
	'C.UTF-8/UTF-8 \\\n'
	'be_BY.UTF-8/UTF-8 \\\n'
	'be_BY/CP1251 \\\n'
	'be_BY@latin/UTF-8 \\\n'
	'ca_AD.UTF-8/UTF-8 \\\n'
	'ca_AD/ISO-8859-15 \\\n'
	'de_DE.UTF-8/UTF-8 \\\n'
	'de_DE/ISO-8859-1 \\\n'
	'de_DE@euro/ISO-8859-15 \\\n'
	'en_GB.UTF-8/UTF-8 \\\n'
	'en_GB/ISO-8859-1 \\\n'
	'en_IL/UTF-8 \\\n'
	'en_US.UTF-8/UTF-8 \\\n'
	'en_US/ISO-8859-1 \\\n'
)

_EXPECTED_LOCALES = [
	'be_BY.UTF-8 UTF-8',
	'be_BY CP1251',
	'be_BY@latin UTF-8',
	'ca_AD.UTF-8 UTF-8',
	'ca_AD ISO-8859-15',
	'de_DE.UTF-8 UTF-8',
	'de_DE ISO-8859-1',
	'de_DE@euro ISO-8859-15',
	'en_GB.UTF-8 UTF-8',
	'en_GB ISO-8859-1',
	'en_IL UTF-8',
	'en_US.UTF-8 UTF-8',
	'en_US ISO-8859-1',
]


def _run_set_locale(
	target: Path,
	sys_lang: str,
	sys_enc: str,
	monkeypatch: pytest.MonkeyPatch,
	locale_gen: str = _LOCALE_GEN,
) -> tuple[str, str]:
	(target / 'etc').mkdir(parents=True)
	(target / 'etc/locale.gen').write_text(locale_gen)

	installation = Installer.__new__(Installer)
	installation.target = target
	# skip the locale-gen run in chroot
	monkeypatch.setattr(installation, 'arch_chroot', lambda cmd: None, raising=False)

	assert installation.set_locale(LocaleConfiguration('us', sys_lang, sys_enc))
	return (
		(target / 'etc/locale.conf').read_text(),
		(target / 'etc/locale.gen').read_text(),
	)


def test_set_locale_bare_utf8_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	locale_conf, locale_gen = _run_set_locale(tmp_path, 'en_IL', 'UTF-8', monkeypatch)

	assert locale_conf == 'LANG=en_IL.UTF-8\n'
	# entry only uncommented, name left as SUPPORTED lists it
	assert 'en_IL UTF-8' in locale_gen
	assert '#en_IL' not in locale_gen


def test_set_locale_suffix_lands_before_modifier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	locale_conf, locale_gen = _run_set_locale(tmp_path, 'be_BY@latin', 'UTF-8', monkeypatch)

	assert locale_conf == 'LANG=be_BY.UTF-8@latin\n'
	assert 'be_BY@latin UTF-8' in locale_gen
	assert '#be_BY@latin' not in locale_gen
	# sibling charset entries untouched
	assert '#be_BY.UTF-8 UTF-8' in locale_gen
	assert '#be_BY CP1251' in locale_gen


def test_set_locale_suffixed_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	locale_conf, locale_gen = _run_set_locale(tmp_path, 'en_GB.UTF-8', 'UTF-8', monkeypatch)

	assert locale_conf == 'LANG=en_GB.UTF-8\n'
	assert '#en_GB ISO-8859-1' in locale_gen


def test_set_locale_non_utf8_fully_qualified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	locale_conf, locale_gen = _run_set_locale(tmp_path, 'en_US', 'ISO-8859-1', monkeypatch)

	assert locale_conf == 'LANG=en_US.ISO-8859-1\n'
	assert 'en_US ISO-8859-1' in locale_gen
	# the UTF-8 sibling is the always-on fallback now, not collateral
	assert '#en_US.UTF-8 UTF-8' not in locale_gen


def _use_disk_supported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	supported = tmp_path / 'SUPPORTED'
	supported.write_text(_DISK_SUPPORTED)
	monkeypatch.setattr(catalog, '_SUPPORTED_PATH', supported)


def _use_upstream_supported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str = _GLIBC_SUPPORTED) -> None:
	# no glibc copy on disk (musl/alpine host), answer the fetch instead
	monkeypatch.setattr(catalog, '_SUPPORTED_PATH', tmp_path / 'absent')
	monkeypatch.setattr(catalog, 'fetch_data_from_url', lambda url, **kw: text)


def test_list_locales_from_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	_use_disk_supported(tmp_path, monkeypatch)

	# C.UTF-8 is compiled into glibc and absent from locale.gen, so it must not
	# reach the menu even though SUPPORTED lists it
	assert catalog.list_locales() == _EXPECTED_LOCALES


def test_list_locales_fetch_matches_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	_use_upstream_supported(tmp_path, monkeypatch)

	# "<locale>/<charset> \" converts to the same form the disk copy uses
	assert catalog.list_locales() == _EXPECTED_LOCALES


def test_list_locales_offline_falls_back_to_minimum(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	def _no_network(url: str, **kwargs: object) -> str:
		raise ValueError(f'Unable to fetch data from url: {url}')

	monkeypatch.setattr(catalog, '_SUPPORTED_PATH', tmp_path / 'absent')
	monkeypatch.setattr(catalog, 'fetch_data_from_url', _no_network)

	assert catalog.list_locales() == catalog._MIN_LOCALES


def test_offered_locales_have_a_locale_gen_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# every locale the menu offers must uncomment a line in the target's
	# locale.gen; a builtin like C.UTF-8 leaking through fails here
	_use_upstream_supported(tmp_path, monkeypatch)
	offered = catalog.list_locales() + catalog._MIN_LOCALES
	locale_gen = ''.join(f'#{entry}  \n' for entry in offered)

	for index, entry in enumerate(offered):
		sys_lang, sys_enc = entry.split()
		locale_conf, _ = _run_set_locale(tmp_path / f'root{index}', sys_lang, sys_enc, monkeypatch, locale_gen)
		assert locale_conf.startswith('LANG=')


def test_encodings_are_scoped_to_the_language(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	_use_disk_supported(tmp_path, monkeypatch)

	# a language with two charsets offers both, UTF-8 first so a language
	# switch lands on it
	assert catalog.list_locale_encodings('de_DE') == ['UTF-8', 'ISO-8859-1']
	# ...and one with no UTF-8 entry offers only what it has
	assert catalog.list_locale_encodings('de_DE@euro') == ['ISO-8859-15']
	assert catalog.list_locale_encodings('ca_AD') == ['UTF-8', 'ISO-8859-15']
	# a name that spells its own codeset leaves nothing to choose
	assert catalog.list_locale_encodings('en_GB.UTF-8') == ['UTF-8']
	assert catalog.list_locale_encodings('en_IL') == ['UTF-8']


def test_every_scoped_pair_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# the invariant the split language/encoding menus have to hold: every pair
	# they can produce names a locale.gen entry. Unscoped, only 866 of the
	# 15030 pairs the two menus could form did.
	_use_disk_supported(tmp_path, monkeypatch)
	langs = [locale.split()[0] for locale in catalog.list_locales()]

	index = 0
	for sys_lang in langs:
		for sys_enc in catalog.list_locale_encodings(sys_lang):
			index += 1
			locale_conf, _ = _run_set_locale(tmp_path / f'root{index}', sys_lang, sys_enc, monkeypatch)
			assert locale_conf.startswith('LANG=')


def test_language_change_drops_an_incompatible_encoding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	_use_disk_supported(tmp_path, monkeypatch)
	monkeypatch.setattr(locale_menu, 'select_locale_lang', lambda preset=None: 'de_DE@euro')

	menu = locale_menu.LocaleMenu(LocaleConfiguration('us', 'en_US.UTF-8', 'UTF-8'))
	assert menu._select_locale_lang('en_US.UTF-8') == 'de_DE@euro'
	# no de_DE@euro UTF-8 entry exists, so the carried-over default goes
	assert menu._menu_item_group.find_by_key('sys_enc').value == 'ISO-8859-15'


def test_language_change_keeps_a_compatible_encoding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	_use_disk_supported(tmp_path, monkeypatch)
	monkeypatch.setattr(locale_menu, 'select_locale_lang', lambda preset=None: 'de_DE')

	menu = locale_menu.LocaleMenu(LocaleConfiguration('us', 'en_US', 'ISO-8859-1'))
	assert menu._select_locale_lang('en_US') == 'de_DE'
	# de_DE has an ISO-8859-1 entry of its own; nothing to correct
	assert menu._menu_item_group.find_by_key('sys_enc').value == 'ISO-8859-1'


def test_set_locale_euro_modifier_without_utf8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# de_DE@euro exists only as ISO-8859-15; the menu now hands over that
	# charset instead of the UTF-8 default it used to carry across
	locale_conf, locale_gen = _run_set_locale(tmp_path, 'de_DE@euro', 'ISO-8859-15', monkeypatch)

	assert locale_conf == 'LANG=de_DE.ISO-8859-15@euro\n'
	assert 'de_DE@euro ISO-8859-15' in locale_gen
	assert '#de_DE@euro' not in locale_gen
	assert '#de_DE ISO-8859-1  ' in locale_gen


def test_set_locale_charset_prefix_is_not_a_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# ca_AD ships ISO-8859-15 only; asking for ISO-8859-1 must fail rather
	# than uncomment the ISO-8859-15 line its name is a prefix of
	(tmp_path / 'etc').mkdir()
	(tmp_path / 'etc/locale.gen').write_text(_LOCALE_GEN)

	installation = Installer.__new__(Installer)
	installation.target = tmp_path
	monkeypatch.setattr(installation, 'arch_chroot', lambda cmd: None, raising=False)

	assert not installation.set_locale(LocaleConfiguration('us', 'ca_AD', 'ISO-8859-1'))
	assert '#ca_AD ISO-8859-15' in (tmp_path / 'etc/locale.gen').read_text()


def test_set_locale_unknown_entry_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	(tmp_path / 'etc').mkdir()
	(tmp_path / 'etc/locale.gen').write_text(_LOCALE_GEN)

	installation = Installer.__new__(Installer)
	installation.target = tmp_path
	monkeypatch.setattr(installation, 'arch_chroot', lambda cmd: None, raising=False)

	assert not installation.set_locale(LocaleConfiguration('us', 'xx_XX', 'UTF-8'))
	assert not (tmp_path / 'etc/locale.conf').exists()


# https://github.com/archlinux/archinstall/issues/3764: en_US.UTF-8 is the
# fallback tools hardcode, so it gets generated alongside any other choice
def test_set_locale_generates_en_us_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	locale_conf, locale_gen = _run_set_locale(tmp_path, 'en_GB', 'UTF-8', monkeypatch)
	assert locale_conf == 'LANG=en_GB.UTF-8\n'
	assert '\nen_GB.UTF-8 UTF-8' in '\n' + locale_gen
	assert '\nen_US.UTF-8 UTF-8' in '\n' + locale_gen
	assert '#en_US ISO-8859-1' in locale_gen


def test_set_locale_en_us_only_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	_, locale_gen = _run_set_locale(tmp_path, 'en_US', 'UTF-8', monkeypatch)
	assert locale_gen.count('en_US.UTF-8 UTF-8') == 1
	assert '#en_US.UTF-8' not in locale_gen


# kbd ships docs and a partialfonts/ subdirectory next to the fonts. Offering
# either writes a FONT= the sd-vconsole hook cannot resolve, and that hook
# errors out rather than warning, so the initramfs build fails.
def test_list_console_fonts_skips_non_fonts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(catalog, '_FONT_DIR', tmp_path)
	(tmp_path / 'partialfonts').mkdir()
	(tmp_path / 'ERRORS').write_text('In iso04.f08 the letters K, and k, are wrong.\n')
	(tmp_path / 'README.Cyrillic').write_text('docs\n')
	# README.psfu carries a font suffix, so only the prefix check excludes it
	for name in ('cyr-sun16.psfu.gz', 'default8x16.psfu.gz', 'alt-8x16.gz', 'arm8.fnt.gz', '161.cp.gz', 'README.psfu'):
		(tmp_path / name).write_bytes(b'')

	# alt-8x16 carries no font extension at all, only compression; the kbd
	# hooks resolve it and so must the menu
	assert catalog.list_console_fonts() == ['161.cp', 'alt-8x16', 'arm8.fnt', 'cyr-sun16', 'default8x16']


# systemd-localed reads the XKB layout from /etc/vconsole.conf in preference to
# the Xorg InputClass since v253, and writes it back there, so the install has
# to put it in both places or localed reports (and later overwrites) a layout
# the install never chose.
def _run_set_keyboard(target: Path, config: LocaleConfiguration) -> str:
	installation = Installer.__new__(Installer)
	installation.target = target

	installation.set_vconsole(config)
	assert installation.set_keyboard(config)
	return (target / 'etc/vconsole.conf').read_text()


def test_xkb_keys_land_in_vconsole(tmp_path: Path) -> None:
	config = LocaleConfiguration(
		'fr',
		'en_US.UTF-8',
		'UTF-8',
		xkb_layout='fr',
		xkb_model='pc105',
		xkb_variant='oss',
		xkb_options='grp:alt_shift_toggle',
	)
	vconsole = _run_set_keyboard(tmp_path, config)

	# the console keymap set_vconsole() owns survives the XKB rewrite
	assert 'KEYMAP=fr\n' in vconsole
	assert 'FONT=default8x16\n' in vconsole
	assert 'XKBLAYOUT=fr\n' in vconsole
	assert 'XKBMODEL=pc105\n' in vconsole
	assert 'XKBVARIANT=oss\n' in vconsole
	assert 'XKBOPTIONS=grp:alt_shift_toggle\n' in vconsole

	xorg = (tmp_path / 'etc/X11/xorg.conf.d/00-keyboard.conf').read_text()
	assert 'Option "XkbLayout" "fr"' in xorg
	assert 'XKB_DEFAULT_LAYOUT=fr\n' in (tmp_path / 'etc/environment').read_text()


def test_xkb_rewrite_drops_stale_keys(tmp_path: Path) -> None:
	with_variant = LocaleConfiguration('fr', 'en_US.UTF-8', 'UTF-8', xkb_layout='fr', xkb_variant='oss')
	_run_set_keyboard(tmp_path, with_variant)

	# second pass without a variant: the key is gone, not kept from the first
	vconsole = _run_set_keyboard(tmp_path, LocaleConfiguration('fr', 'en_US.UTF-8', 'UTF-8', xkb_layout='fr'))
	assert 'XKBVARIANT' not in vconsole
	assert vconsole.count('XKBLAYOUT=fr') == 1


# The X11 lists come from xkeyboard-config's own registry, the same file
# localectl parses to answer list-x11-keymap-*; the fetch is for hosts that
# ship no xkeyboard-config at all.
_REGISTRY = """<?xml version="1.0" encoding="UTF-8"?>
<xkbConfigRegistry version="1.1">
  <modelList>
    <model><configItem><name>pc105</name></configItem></model>
  </modelList>
  <layoutList>
    <layout>
      <configItem><name>be</name></configItem>
      <variantList>
        <variant><configItem><name>oss</name></configItem></variant>
        <variant><configItem><name>nodeadkeys</name></configItem></variant>
      </variantList>
    </layout>
  </layoutList>
  <optionList>
    <group><configItem><name>caps</name></configItem>
      <option><configItem><name>caps:escape</name></configItem></option>
    </group>
  </optionList>
</xkbConfigRegistry>
"""


@pytest.fixture(autouse=True)
def _clear_x11_registry_cache() -> Iterator[None]:
	# the parse is cached for the menu's repeated variant lookups, so a test
	# swapping the source must leak it in neither direction
	catalog._load_x11_registry.cache_clear()
	yield
	catalog._load_x11_registry.cache_clear()


@pytest.fixture
def local_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
	path = tmp_path / 'evdev.xml'
	path.write_text(_REGISTRY)
	monkeypatch.setattr(catalog, '_X11_RULES_PATHS', (path,))
	monkeypatch.setattr(catalog, '_fetch_x11_registry', lambda: pytest.fail('fetched with a local registry present'))
	return path


def test_x11_lists_read_the_local_registry(local_registry: Path) -> None:
	assert catalog.list_x11_keyboard_languages() == ['be']
	assert catalog.list_x11_keyboard_models() == ['pc105']
	assert catalog.list_x11_keyboard_variants('be') == ['oss', 'nodeadkeys']
	# unknown and empty layouts are not an error, they have no variants
	assert catalog.list_x11_keyboard_variants('zz') == []
	assert catalog.list_x11_keyboard_variants('') == []


def test_x11_options_skip_group_headings(local_registry: Path) -> None:
	# localectl also prints the group names (caps, grp, ...); XkbOptions takes
	# only the group:option leaves, so offering a bare group is offering junk
	assert catalog.list_x11_keyboard_options() == ['caps:escape']


def test_x11_registry_falls_back_to_the_fetch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(catalog, '_X11_RULES_PATHS', (tmp_path / 'missing.xml',))
	monkeypatch.setattr(catalog, '_fetch_x11_registry', lambda: ET.fromstring(_REGISTRY))  # noqa: S314 - fixture XML written by this test

	assert catalog.list_x11_keyboard_languages() == ['be']


def test_x11_registry_survives_a_broken_local_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	broken = tmp_path / 'evdev.xml'
	broken.write_text('<xkbConfigRegistry')
	monkeypatch.setattr(catalog, '_X11_RULES_PATHS', (broken,))
	monkeypatch.setattr(catalog, '_fetch_x11_registry', lambda: ET.fromstring(_REGISTRY))  # noqa: S314 - fixture XML written by this test

	assert catalog.list_x11_keyboard_languages() == ['be']


def test_failed_fetch_is_retried_not_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# a blip on the fetch path must not leave every keymap list empty for the
	# rest of the run: the parse is cached, the failure is not
	attempts = []

	def failing_fetch() -> None:
		attempts.append(1)

	monkeypatch.setattr(catalog, '_X11_RULES_PATHS', (tmp_path / 'missing.xml',))
	monkeypatch.setattr(catalog, '_fetch_x11_registry', failing_fetch)

	assert catalog.list_x11_keyboard_languages() == []
	assert catalog.list_x11_keyboard_models() == []
	assert len(attempts) == 2

	# and once it comes back, the parse is cached for the calls after it
	monkeypatch.setattr(catalog, '_fetch_x11_registry', lambda: ET.fromstring(_REGISTRY))  # noqa: S314 - fixture XML written by this test
	assert catalog.list_x11_keyboard_languages() == ['be']
	monkeypatch.setattr(catalog, '_fetch_x11_registry', lambda: pytest.fail('re-fetched a registry already parsed'))
	assert catalog.list_x11_keyboard_models() == ['pc105']
