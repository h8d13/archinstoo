import pytest

from archinstoo.lib.pm import bootstrap

# Slice of the real Arch Ports forge/ index (S3): absolute hrefs, and the
# keyring sits next to its own .sig
_PORTS_INDEX = """
<a href="/arch/forge/os/aarch64/archports-keyring-20260731-1-any.pkg.tar.zst">archports-keyring-20260731-1-any.pkg.tar.zst</a>
<a href="/arch/forge/os/aarch64/archports-keyring-20260831-1-any.pkg.tar.zst">archports-keyring-20260831-1-any.pkg.tar.zst</a>
<a href="/arch/forge/os/aarch64/archports-keyring-20260831-1-any.pkg.tar.zst.sig">archports-keyring-20260831-1-any.pkg.tar.zst.sig</a>
"""

_X86_INDEX = """
<a href="archlinux-keyring-20260707.1-1-any.pkg.tar.zst">archlinux-keyring-20260707.1-1-any.pkg.tar.zst</a>
<a href="archlinux-keyring-20260707.1-1-any.pkg.tar.zst.sig">sig</a>
"""


def test_sources_x86(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr('platform.machine', lambda: 'x86_64')

	src = bootstrap._sources()

	assert src.keyring_mirror == bootstrap._KEYRING_MIRROR
	assert (src.keyring_pkg, src.keyring) == ('archlinux-keyring', 'archlinux')


def test_sources_aarch64(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr('platform.machine', lambda: 'aarch64')

	src = bootstrap._sources()

	assert src.keyring_mirror == bootstrap._PORTS_KEYRING_MIRROR
	assert (src.keyring_pkg, src.keyring) == ('archports-keyring', 'archports')
	# same upstream conf as x86_64, the port only differs in servers
	assert src.pacman_conf == bootstrap._PACMAN_CONF_URL


def test_latest_keyring_url_ports(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(bootstrap, 'fetch_data_from_url', lambda url, **kw: _PORTS_INDEX)

	url = bootstrap._latest_keyring_url(bootstrap._PORTS_KEYRING_MIRROR, 'archports-keyring')

	# newest of the two, filename only despite the absolute href
	assert url == f'{bootstrap._PORTS_KEYRING_MIRROR}archports-keyring-20260831-1-any.pkg.tar.zst'


def test_latest_keyring_url_x86(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(bootstrap, 'fetch_data_from_url', lambda url, **kw: _X86_INDEX)

	url = bootstrap._latest_keyring_url(bootstrap._KEYRING_MIRROR, 'archlinux-keyring')

	assert url == f'{bootstrap._KEYRING_MIRROR}archlinux-keyring-20260707.1-1-any.pkg.tar.zst'


def test_latest_keyring_url_missing(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(bootstrap, 'fetch_data_from_url', lambda url, **kw: '<a href="pacman-7.0.0-1-aarch64.pkg.tar.zst">pacman</a>')

	with pytest.raises(RuntimeError, match='archports-keyring package not found'):
		bootstrap._latest_keyring_url(bootstrap._PORTS_KEYRING_MIRROR, 'archports-keyring')


def test_mirrorlist_is_the_ports_server_off_x86(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr('platform.machine', lambda: 'aarch64')

	assert f'Server = {bootstrap._PORTS_SERVER}' in bootstrap._build_mirrorlist()
