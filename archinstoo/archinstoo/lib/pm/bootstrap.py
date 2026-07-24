import json
import platform
import re
import tarfile
import tempfile
from compression.zstd import ZstdFile
from pathlib import Path
from typing import NamedTuple

from archinstoo.lib.output import info
from archinstoo.lib.pacman import Pacman
from archinstoo.lib.pathnames import MIRRORLIST, PACMAN_CONF
from archinstoo.lib.utils.net import download_file_from_url, fetch_data_from_url

# Sources we pull from when the host isn't Arch and ships pacman but no config.
# (_PACMAN_CONF_URL is the same upstream default lib.pacman.reset_conf resets to.)
_MIRROR_STATUS_URL = 'https://archlinux.org/mirrors/status/json/'
_PACMAN_CONF_URL = 'https://gitlab.archlinux.org/archlinux/packaging/packages/pacman/-/raw/main/pacman.conf'
_KEYRING_MIRROR = 'https://geo.mirror.pkgbuild.com/core/os/x86_64/'

# archlinux.org ships x86_64 only. Off it, follow archlinuxarm.org: $arch/$repo
# mirror layout, its own repos and its own signing key, so conf + mirrorlist +
# keyring all have to move together.
_ARM_PACMAN_CONF_URL = 'https://raw.githubusercontent.com/archlinuxarm/PKGBUILDs/master/core/pacman/pacman.conf'
_ARM_MIRRORLIST_URL = 'https://raw.githubusercontent.com/archlinuxarm/PKGBUILDs/master/core/pacman-mirrorlist/mirrorlist'
_ARM_KEYRING_MIRROR = 'http://mirror.archlinuxarm.org/{arch}/core/'

_TRUSTDB = Path('/etc/pacman.d/gnupg/trustdb.gpg')
_KEYRING_DIR = Path('/usr/share/pacman/keyrings')

# pacman expects these to exist; a bare host that only ships the binary won't
# have them, so we create them up front before writing any config.
_PACMAN_DIRS = (
	Path('/etc/pacman.d/gnupg'),
	Path('/etc/pacman.d/hooks'),
	Path('/var/lib/pacman'),
	Path('/var/cache/pacman/pkg'),
)


class _Sources(NamedTuple):
	pacman_conf: str
	keyring_mirror: str
	keyring_pkg: str
	keyring: str  # pacman-key --populate name, and <name>.gpg in _KEYRING_DIR


def _sources() -> _Sources:
	# Single branch for the whole bootstrap: another arch means one more entry
	# here, not conditionals scattered down the file. platform, not SysInfo:
	# this runs before the lib's deps are bootstrapped.
	arch = platform.machine()
	if arch == 'x86_64':
		return _Sources(_PACMAN_CONF_URL, _KEYRING_MIRROR, 'archlinux-keyring', 'archlinux')
	return _Sources(_ARM_PACMAN_CONF_URL, _ARM_KEYRING_MIRROR.format(arch=arch), 'archlinuxarm-keyring', 'archlinuxarm')


def _has_repos() -> bool:
	# True only if pacman.conf already declares a real repo, not just [options].
	if not PACMAN_CONF.exists():
		return False
	return bool(re.search(r'^\[(?!options\b)[\w-]+\]', PACMAN_CONF.read_text(), re.MULTILINE))


def _build_mirrorlist() -> str:
	if platform.machine() != 'x86_64':
		# No mirror-status API off x86_64; the packaged mirrorlist already ships
		# its geo-balanced server uncommented, so take it verbatim.
		info(f'Fetching mirrorlist from {_ARM_MIRRORLIST_URL}...')
		return fetch_data_from_url(_ARM_MIRRORLIST_URL, timeout=15)

	info(f'Fetching mirror status from {_MIRROR_STATUS_URL}...')
	data = json.loads(fetch_data_from_url(_MIRROR_STATUS_URL, timeout=15))
	# Emit every active http/https mirror; ranking happens later, not here.
	servers = [f'Server = {m["url"]}$repo/os/$arch' for m in data.get('urls', []) if m.get('active') and m.get('protocol') in ('https', 'http')]
	return '\n'.join(['# Arch mirrors fetched by archinstoo bootstrap', *servers]) + '\n'


def pacman_conf() -> None:
	# Give pacman a working config + mirrorlist on a non-Arch host. Must run
	# before keyring_init(): pacman-key reads /etc/pacman.conf for its GPGDir.
	for d in _PACMAN_DIRS:
		d.mkdir(parents=True, exist_ok=True)

	if _has_repos():
		return

	info('Configuring pacman for non-Arch host...')
	MIRRORLIST.write_text(_build_mirrorlist())

	conf_url = _sources().pacman_conf
	info(f'Fetching pacman.conf from {conf_url}...')
	conf = fetch_data_from_url(conf_url)
	# DownloadUser = alpm doesn't exist off Arch; drop it so pacman can run.
	conf = re.sub(r'^DownloadUser\s*=.*\n', '', conf, flags=re.MULTILINE)
	# Packaging templates leave Architecture = @CARCH@ for build time to fill;
	# no-op on a conf that ships already substituted.
	conf = conf.replace('@CARCH@', platform.machine())
	PACMAN_CONF.write_text(conf)


def _latest_keyring_url(mirror: str, pkg_name: str) -> str:
	page = fetch_data_from_url(mirror)
	# .zst on Arch, .xz on Arch Linux ARM
	pkgs: list[str] = re.findall(rf'href="({re.escape(pkg_name)}-[^"]+\.pkg\.tar\.(?:zst|xz))"', page)
	if not pkgs:
		raise RuntimeError(f'{pkg_name} package not found on {mirror}')
	# Lexical order tracks the version-date suffix, so max == newest.
	return mirror + max(pkgs)


def keyring_init() -> None:
	# Install + populate the distro keyring so -Sy can verify signatures at the
	# upstream default. No-op once the keyring and an initialised trustdb both
	# exist: Debian ships the keyring files but never inits the trustdb.
	src = _sources()

	if (_KEYRING_DIR / f'{src.keyring}.gpg').exists() and _TRUSTDB.exists():
		return

	url = _latest_keyring_url(src.keyring_mirror, src.keyring_pkg)
	info(f'Downloading keyring {url}...')
	with tempfile.TemporaryDirectory() as tmp:
		root = Path(tmp)
		pkg = root / url.rsplit('/', 1)[-1]
		download_file_from_url(url, pkg)

		info('Extracting keyring...')
		if pkg.suffix == '.zst':
			with ZstdFile(pkg) as raw, tarfile.open(fileobj=raw, mode='r|') as t:
				t.extractall(root, filter='data')
		else:
			with tarfile.open(pkg, mode='r:xz') as t:
				t.extractall(root, filter='data')

		_KEYRING_DIR.mkdir(parents=True, exist_ok=True)
		for key in (root / 'usr/share/pacman/keyrings').iterdir():
			key.copy_into(_KEYRING_DIR, preserve_metadata=True)

	info('Initialising pacman-key...')
	Pacman.run('--init', default_cmd='pacman-key', peek_output=True)
	Pacman.run(f'--populate --populate-from {_KEYRING_DIR} {src.keyring}', default_cmd='pacman-key', peek_output=True)
