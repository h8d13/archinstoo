import pytest

from archinstoo.lib.pm import bootstrap

# Slice of a real archlinuxarm.org core/ index: .xz, not .zst, and
# archlinuxarm-keyring sits right next to archlinux-keyring.
_ARM_INDEX = """
<a href="archlinux-keyring-20260707.1-1-any.pkg.tar.xz">archlinux-keyring-20260707.1-1-any.pkg.tar.xz</a>
<a href="archlinux-keyring-20260707.1-1-any.pkg.tar.xz.sig">sig</a>
<a href="archlinuxarm-keyring-20240418-2-any.pkg.tar.xz">archlinuxarm-keyring-20240418-2-any.pkg.tar.xz</a>
<a href="archlinuxarm-keyring-20240419-2-any.pkg.tar.xz">archlinuxarm-keyring-20240419-2-any.pkg.tar.xz</a>
<a href="archlinuxarm-keyring-20240419-2-any.pkg.tar.xz.sig">sig</a>
"""

_X86_INDEX = """
<a href="archlinux-keyring-20260707.1-1-any.pkg.tar.zst">archlinux-keyring-20260707.1-1-any.pkg.tar.zst</a>
<a href="archlinux-keyring-20260707.1-1-any.pkg.tar.zst.sig">sig</a>
"""


def test_sources_x86(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(bootstrap.platform, 'machine', lambda: 'x86_64')

	src = bootstrap._sources()

	assert src.keyring_mirror == bootstrap._KEYRING_MIRROR
	assert (src.keyring_pkg, src.keyring) == ('archlinux-keyring', 'archlinux')


def test_sources_aarch64(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(bootstrap.platform, 'machine', lambda: 'aarch64')

	src = bootstrap._sources()

	assert src.keyring_mirror == 'http://mirror.archlinuxarm.org/aarch64/core/'
	assert (src.keyring_pkg, src.keyring) == ('archlinuxarm-keyring', 'archlinuxarm')
	assert src.pacman_conf == bootstrap._ARM_PACMAN_CONF_URL


def test_latest_keyring_url_arm(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(bootstrap, 'fetch_data_from_url', lambda url, **kw: _ARM_INDEX)

	url = bootstrap._latest_keyring_url('http://arm.test/aarch64/core/', 'archlinuxarm-keyring')

	# newest of the two, and not the neighbouring archlinux-keyring
	assert url == 'http://arm.test/aarch64/core/archlinuxarm-keyring-20240419-2-any.pkg.tar.xz'


def test_latest_keyring_url_x86(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(bootstrap, 'fetch_data_from_url', lambda url, **kw: _X86_INDEX)

	url = bootstrap._latest_keyring_url(bootstrap._KEYRING_MIRROR, 'archlinux-keyring')

	assert url == f'{bootstrap._KEYRING_MIRROR}archlinux-keyring-20260707.1-1-any.pkg.tar.zst'


def test_latest_keyring_url_missing(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(bootstrap, 'fetch_data_from_url', lambda url, **kw: '<a href="pacman-7.0.0-1-aarch64.pkg.tar.xz">pacman</a>')

	with pytest.raises(RuntimeError, match='archlinuxarm-keyring package not found'):
		bootstrap._latest_keyring_url('http://arm.test/aarch64/core/', 'archlinuxarm-keyring')


def test_mirrorlist_taken_verbatim_off_x86(monkeypatch: pytest.MonkeyPatch) -> None:
	mirrorlist = '# Arch Linux ARM repository mirrorlist\nServer = http://mirror.archlinuxarm.org/$arch/$repo\n'
	monkeypatch.setattr(bootstrap.platform, 'machine', lambda: 'aarch64')
	monkeypatch.setattr(bootstrap, 'fetch_data_from_url', lambda url, **kw: mirrorlist)

	assert bootstrap._build_mirrorlist() == mirrorlist
