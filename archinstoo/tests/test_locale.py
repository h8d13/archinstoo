# glibc's SUPPORTED lists UTF-8-only locales without a ".UTF-8" suffix in the
# first column (no other charset variant exists to disambiguate from). Written
# bare to locale.conf, tools sniffing LANG for "UTF-8" (tmux et al.) drop to
# legacy charsets. set_locale writes the fully qualified name to locale.conf;
# it resolves against the bare compiled locale because localedef registers a
# normalized-codeset alias for codeset-less names (glibc locarchive.c).
# All entries below are verbatim from /usr/share/i18n/SUPPORTED.

from typing import TYPE_CHECKING

from archinstoo.lib.installer import Installer
from archinstoo.lib.localization import utils as loc_utils
from archinstoo.lib.menu import locale_menu
from archinstoo.lib.models.locale import LocaleConfiguration

if TYPE_CHECKING:
	from pathlib import Path

	import pytest


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
	assert '#en_US.UTF-8 UTF-8' in locale_gen


def _use_disk_supported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	supported = tmp_path / 'SUPPORTED'
	supported.write_text(_DISK_SUPPORTED)
	monkeypatch.setattr(loc_utils, '_SUPPORTED_PATH', supported)


def _use_upstream_supported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str = _GLIBC_SUPPORTED) -> None:
	# no glibc copy on disk (musl/alpine host), answer the fetch instead
	monkeypatch.setattr(loc_utils, '_SUPPORTED_PATH', tmp_path / 'absent')
	monkeypatch.setattr(loc_utils, 'fetch_data_from_url', lambda url, **kw: text)


def test_list_locales_from_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	_use_disk_supported(tmp_path, monkeypatch)

	# C.UTF-8 is compiled into glibc and absent from locale.gen, so it must not
	# reach the menu even though SUPPORTED lists it
	assert loc_utils.list_locales() == _EXPECTED_LOCALES


def test_list_locales_fetch_matches_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	_use_upstream_supported(tmp_path, monkeypatch)

	# "<locale>/<charset> \" converts to the same form the disk copy uses
	assert loc_utils.list_locales() == _EXPECTED_LOCALES


def test_list_locales_offline_falls_back_to_minimum(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	def _no_network(url: str, **kwargs: object) -> str:
		raise ValueError(f'Unable to fetch data from url: {url}')

	monkeypatch.setattr(loc_utils, '_SUPPORTED_PATH', tmp_path / 'absent')
	monkeypatch.setattr(loc_utils, 'fetch_data_from_url', _no_network)

	assert loc_utils.list_locales() == loc_utils._MIN_LOCALES


def test_offered_locales_have_a_locale_gen_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# every locale the menu offers must uncomment a line in the target's
	# locale.gen; a builtin like C.UTF-8 leaking through fails here
	_use_upstream_supported(tmp_path, monkeypatch)
	offered = loc_utils.list_locales() + loc_utils._MIN_LOCALES
	locale_gen = ''.join(f'#{entry}  \n' for entry in offered)

	for index, entry in enumerate(offered):
		sys_lang, sys_enc = entry.split()
		locale_conf, _ = _run_set_locale(tmp_path / f'root{index}', sys_lang, sys_enc, monkeypatch, locale_gen)
		assert locale_conf.startswith('LANG=')


def test_encodings_are_scoped_to_the_language(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	_use_disk_supported(tmp_path, monkeypatch)

	# a language with two charsets offers both, UTF-8 first so a language
	# switch lands on it
	assert loc_utils.list_locale_encodings('de_DE') == ['UTF-8', 'ISO-8859-1']
	# ...and one with no UTF-8 entry offers only what it has
	assert loc_utils.list_locale_encodings('de_DE@euro') == ['ISO-8859-15']
	assert loc_utils.list_locale_encodings('ca_AD') == ['UTF-8', 'ISO-8859-15']
	# a name that spells its own codeset leaves nothing to choose
	assert loc_utils.list_locale_encodings('en_GB.UTF-8') == ['UTF-8']
	assert loc_utils.list_locale_encodings('en_IL') == ['UTF-8']


def test_every_scoped_pair_resolves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# the invariant the split language/encoding menus have to hold: every pair
	# they can produce names a locale.gen entry. Unscoped, only 866 of the
	# 15030 pairs the two menus could form did.
	_use_disk_supported(tmp_path, monkeypatch)
	langs = [locale.split()[0] for locale in loc_utils.list_locales()]

	index = 0
	for sys_lang in langs:
		for sys_enc in loc_utils.list_locale_encodings(sys_lang):
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
