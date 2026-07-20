# glibc's SUPPORTED lists UTF-8-only locales without a ".UTF-8" suffix in the
# first column (no other charset variant exists to disambiguate from). Written
# bare to locale.conf, tools sniffing LANG for "UTF-8" (tmux et al.) drop to
# legacy charsets. set_locale writes the fully qualified name to locale.conf;
# it resolves against the bare compiled locale because localedef registers a
# normalized-codeset alias for codeset-less names (glibc locarchive.c).
# All entries below are verbatim from /usr/share/i18n/SUPPORTED.

from typing import TYPE_CHECKING

from archinstoo.lib.installer import Installer
from archinstoo.lib.models.locale import LocaleConfiguration

if TYPE_CHECKING:
	from pathlib import Path

	import pytest


# Arch's generated /etc/locale.gen keeps the trailing spaces from SUPPORTED
_LOCALE_GEN = (
	'#be_BY.UTF-8 UTF-8  \n'
	'#be_BY CP1251  \n'
	'#be_BY@latin UTF-8  \n'
	'#en_GB.UTF-8 UTF-8  \n'
	'#en_GB ISO-8859-1  \n'
	'#en_IL UTF-8  \n'
	'#en_US.UTF-8 UTF-8  \n'
	'#en_US ISO-8859-1  \n'
)


def _run_set_locale(
	target: Path,
	sys_lang: str,
	sys_enc: str,
	monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, str]:
	(target / 'etc').mkdir()
	(target / 'etc/locale.gen').write_text(_LOCALE_GEN)

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


def test_set_locale_unknown_entry_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	(tmp_path / 'etc').mkdir()
	(tmp_path / 'etc/locale.gen').write_text(_LOCALE_GEN)

	installation = Installer.__new__(Installer)
	installation.target = tmp_path
	monkeypatch.setattr(installation, 'arch_chroot', lambda cmd: None, raising=False)

	assert not installation.set_locale(LocaleConfiguration('us', 'xx_XX', 'UTF-8'))
	assert not (tmp_path / 'etc/locale.conf').exists()
