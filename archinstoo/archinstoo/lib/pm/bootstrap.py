import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from compression.zstd import ZstdFile
from pathlib import Path

from archinstoo.lib.output import info

# Sources we pull from when the host isn't Arch and ships pacman but no config.
_MIRROR_STATUS_URL = 'https://archlinux.org/mirrors/status/json/'
_PACMAN_CONF_URL = 'https://gitlab.archlinux.org/archlinux/packaging/packages/pacman/-/raw/main/pacman.conf'
_KEYRING_MIRROR = 'https://geo.mirror.pkgbuild.com/core/os/x86_64/'

_PACMAN_CONF = Path('/etc/pacman.conf')
_MIRRORLIST = Path('/etc/pacman.d/mirrorlist')
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


def _fetch(url: str, timeout: int = 30) -> str:
	with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - fixed https upstream URLs
		return str(resp.read().decode('utf-8'))


def _has_repos() -> bool:
	# True only if pacman.conf already declares a real repo, not just [options].
	if not _PACMAN_CONF.exists():
		return False
	return bool(re.search(r'^\[(?!options\b)[\w-]+\]', _PACMAN_CONF.read_text(), re.MULTILINE))


def _build_mirrorlist() -> str:
	info(f'Fetching mirror status from {_MIRROR_STATUS_URL}...')
	data = json.loads(_fetch(_MIRROR_STATUS_URL, timeout=15))
	# score < 100 drops dead/slow mirrors; lower is better in the status feed.
	servers = [
		f'Server = {m["url"]}$repo/os/$arch'
		for m in data.get('urls', [])
		if m.get('active') and m.get('protocol') in ('https', 'http') and m.get('score') is not None and m['score'] < 100
	]
	return '\n'.join(['# Arch mirrors fetched by archinstoo bootstrap', *servers]) + '\n'


def pacman_conf() -> None:
	# Give pacman a working config + mirrorlist on a non-Arch host. Must run
	# before keyring_init(): pacman-key reads /etc/pacman.conf for its GPGDir.
	for d in _PACMAN_DIRS:
		d.mkdir(parents=True, exist_ok=True)

	if _has_repos():
		return

	info('Configuring pacman for non-Arch host...')
	_MIRRORLIST.write_text(_build_mirrorlist())

	info(f'Fetching pacman.conf from {_PACMAN_CONF_URL}...')
	conf = _fetch(_PACMAN_CONF_URL)
	# DownloadUser = alpm doesn't exist off Arch; drop it so pacman can run.
	conf = re.sub(r'^DownloadUser\s*=.*\n', '', conf, flags=re.MULTILINE)
	_PACMAN_CONF.write_text(conf)


def _latest_keyring_url() -> str:
	page = _fetch(_KEYRING_MIRROR)
	pkgs: list[str] = re.findall(r'href="(archlinux-keyring-[^"]+\.zst)"', page)
	if not pkgs:
		raise RuntimeError('archlinux-keyring package not found on mirror')
	# Lexical sort tracks the version-date suffix, so last == newest.
	return _KEYRING_MIRROR + sorted(pkgs)[-1]


def keyring_init() -> None:
	# Install + populate the Arch keyring so -Sy can verify signatures at the
	# upstream default. No-op once the keyring and an initialised trustdb both
	# exist: Debian ships the keyring files but never inits the trustdb.
	if (_KEYRING_DIR / 'archlinux.gpg').exists() and _TRUSTDB.exists():
		return

	url = _latest_keyring_url()
	info(f'Downloading keyring {url}...')
	with tempfile.TemporaryDirectory() as tmp:
		root = Path(tmp)
		pkg = root / 'keyring.pkg.tar.zst'
		urllib.request.urlretrieve(url, pkg)  # noqa: S310 - url is the geo mirror, https only

		info('Extracting keyring...')
		with ZstdFile(pkg) as raw, tarfile.open(fileobj=raw, mode='r|') as t:
			t.extractall(root, filter='data')

		_KEYRING_DIR.mkdir(parents=True, exist_ok=True)
		for key in (root / 'usr/share/pacman/keyrings').iterdir():
			shutil.copy2(key, _KEYRING_DIR / key.name)

	info('Initialising pacman-key...')
	subprocess.run(['pacman-key', '--init'], check=True)  # noqa: S607 - pacman-key from $PATH, fixed args
	subprocess.run(['pacman-key', '--populate', '--populate-from', str(_KEYRING_DIR), 'archlinux'], check=True)  # noqa: S603, S607 - pacman-key from $PATH, fixed args
