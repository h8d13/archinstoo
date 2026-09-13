import json
import re
import tarfile
import tempfile
from compression.zstd import ZstdFile
from pathlib import Path
from typing import NamedTuple

from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.output import debug, info
from archinstoo.lib.pm.pacman import MIRRORLIST, PACMAN_CONF, PACMAN_GNUPG, Pacman
from archinstoo.lib.utils.net import download_file_from_url, fetch_data_from_url

# Sources we pull from when the host isn't Arch and ships pacman but no config.
# (_PACMAN_CONF_URL is the same upstream default pm.pacman.reset_conf resets to.)
_MIRROR_STATUS_URL = 'https://archlinux.org/mirrors/status/json/'
_PACMAN_CONF_URL = 'https://gitlab.archlinux.org/archlinux/packaging/packages/pacman/-/raw/main/pacman.conf'
_KEYRING_MIRROR = 'https://geo.mirror.pkgbuild.com/core/os/x86_64/'

# archlinux.org ships x86_64 only. aarch64 follows Arch Ports (drzee.net):
# same $repo/os/$arch layout and upstream conf, one server instead of a
# mirror list, a forge repo on top, and its own signing key shipped there.
_PORTS_SERVER = 'https://arch-linux-repo.drzee.net/arch/$repo/os/$arch'
_PORTS_KEYRING_MIRROR = 'https://arch-linux-repo.drzee.net/arch/forge/os/aarch64/'

_TRUSTDB = PACMAN_GNUPG / 'trustdb.gpg'
_KEYRING_DIR = Path('/usr/share/pacman/keyrings')

# pacman expects these to exist; a bare host that only ships the binary won't
# have them, so we create them up front before writing any config.
_PACMAN_DIRS = (
	PACMAN_GNUPG,
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
	# here, not conditionals scattered down the file.
	if SysInfo.arch() == 'x86_64':
		return _Sources(_PACMAN_CONF_URL, _KEYRING_MIRROR, 'archlinux-keyring', 'archlinux')
	return _Sources(_PACMAN_CONF_URL, _PORTS_KEYRING_MIRROR, 'archports-keyring', 'archports')


def _has_repos() -> bool:
	# True only if pacman.conf already declares a real repo, not just [options].
	if not PACMAN_CONF.exists():
		return False
	return bool(re.search(r'^\[(?!options\b)[\w-]+\]', PACMAN_CONF.read_text(), re.MULTILINE))


def _build_mirrorlist() -> str:
	if SysInfo.arch() != 'x86_64':
		# Arch Ports has no mirror network, one S3-backed server
		return f'# Arch Ports, fetched by archinstoo bootstrap\nServer = {_PORTS_SERVER}\n'

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
	conf = conf.replace('@CARCH@', SysInfo.arch())
	if SysInfo.arch() != 'x86_64':
		# upstream conf knows core/extra; the port adds forge ahead of them
		conf = conf.replace('[core]\n', f'[forge]\nInclude = {MIRRORLIST}\n\n[core]\n', 1)
	PACMAN_CONF.write_text(conf)


def _latest_keyring_url(mirror: str, pkg_name: str) -> str:
	page = fetch_data_from_url(mirror)
	# hrefs are bare filenames on archlinux.org mirrors, absolute paths on
	# the Arch Ports S3 index: keep the filename either way
	pkgs: list[str] = re.findall(rf'href="(?:[^"]*/)?({re.escape(pkg_name)}-[^"/]+\.pkg\.tar\.zst)"', page)
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
		debug(f'{src.keyring} keyring and trustdb present, skipping keyring bootstrap')
		return

	url = _latest_keyring_url(src.keyring_mirror, src.keyring_pkg)
	info(f'Downloading keyring {url}...')
	with tempfile.TemporaryDirectory() as tmp:
		root = Path(tmp)
		pkg = root / url.rsplit('/', 1)[-1]
		download_file_from_url(url, pkg)

		info('Extracting keyring...')
		with ZstdFile(pkg) as raw, tarfile.open(fileobj=raw, mode='r|') as t:
			t.extractall(root, filter='data')

		_KEYRING_DIR.mkdir(parents=True, exist_ok=True)
		for key in (root / 'usr/share/pacman/keyrings').iterdir():
			key.copy_into(_KEYRING_DIR, preserve_metadata=True)

	info('Initialising pacman-key...')
	Pacman.run('--init', default_cmd='pacman-key', peek_output=True)
	Pacman.run(f'--populate --populate-from {_KEYRING_DIR} {src.keyring}', default_cmd='pacman-key', peek_output=True)
