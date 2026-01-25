import importlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

PACMAN_CONF = Path('/etc/pacman.conf')
PACMAN_D = Path('/etc/pacman.d')
MIRRORLIST = PACMAN_D / 'mirrorlist'
KEYRING_DIR = Path('/usr/share/pacman/keyrings')
ARCHLINUX_KEYRING = KEYRING_DIR / 'archlinux.gpg'

DEFAULT_MIRROR = 'https://geo.mirror.pkgbuild.com'

DEFAULT_MIRRORS = """\
# Default Arch Linux mirrors for bootstrap
Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch
Server = https://mirror.rackspace.com/archlinux/$repo/os/$arch
Server = https://mirrors.kernel.org/archlinux/$repo/os/$arch
"""

PACMAN_CONF_URL = 'https://gitlab.archlinux.org/archlinux/packaging/packages/pacman/-/raw/main/pacman.conf'


class Os:
	@staticmethod
	def set_env(key: str, value: str) -> None:
		os.environ[key] = value

	@staticmethod
	def get_env(key: str, default: str | None = None) -> str | None:
		return os.environ.get(key, default)

	@staticmethod
	def has_env(key: str) -> bool:
		return key in os.environ


def is_venv() -> bool:
	return sys.prefix != getattr(sys, 'base_prefix', sys.prefix)


def _run_script(script: str) -> None:
	importlib.import_module(f'archinstall.scripts.{script}')


def reload_python() -> None:
	# dirty python trick to reload any changed library modules
	# skip reload during testing to avoid running system archinstall
	if 'pytest' in sys.modules:
		return
	os.execv(sys.executable, [sys.executable, '-m', 'archinstall'] + sys.argv[1:])


def is_root() -> bool:
	return os.getuid() == 0


def running_from_host() -> bool:
	# returns True when not on the ISO
	return not Path('/run/archiso').exists()


def clean_cache(root_dir: str) -> None:
	from ..output import info

	deleted = []

	info('Cleaning up...')
	for dirpath, dirnames, _ in os.walk(root_dir):
		for dirname in dirnames:
			if dirname.lower() == '__pycache__':
				full_path = os.path.join(dirpath, dirname)
				try:
					shutil.rmtree(full_path)
					deleted.append(full_path)
				except Exception as e:
					info(f'Failed to delete {full_path}: {e}')

	if not deleted:
		info('No cache folders found.')
	else:
		info(f'Done. {len(deleted)} cache folder(s) deleted.')


def _has_repos_configured() -> bool:
	"""Check if pacman.conf has any repos enabled (uncommented [reponame] sections)."""
	if not PACMAN_CONF.exists():
		return False

	content = PACMAN_CONF.read_text()
	if not content.strip():
		return False

	# Look for uncommented repo sections like [core], [extra], etc.
	# Ignore [options] section
	repo_pattern = re.compile(r'^\[(?!options\])[\w-]+\]', re.MULTILINE)
	return bool(repo_pattern.search(content))


def _fetch_pacman_conf() -> str:
	"""Fetch official pacman.conf and adjust for non-Arch host."""
	from ..output import info

	info(f'Fetching pacman.conf from {PACMAN_CONF_URL}...')
	with urllib.request.urlopen(PACMAN_CONF_URL, timeout=30) as resp:
		content = resp.read().decode('utf-8')

	# Relax SigLevel for bootstrapping on non-Arch hosts
	content = re.sub(
		r'^SigLevel\s*=.*$',
		'SigLevel = Never',
		content,
		flags=re.MULTILINE,
	)

	# Remove DownloadUser (alpm user won't exist on non-Arch)
	content = re.sub(
		r'^DownloadUser\s*=.*\n',
		'',
		content,
		flags=re.MULTILINE,
	)

	return content


def _fetch_keyring_package_url() -> str:
	"""Find the latest archlinux-keyring package URL from the mirror."""
	import html.parser

	class LinkParser(html.parser.HTMLParser):
		def __init__(self) -> None:
			super().__init__()
			self.links: list[str] = []

		def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
			if tag == 'a':
				for name, value in attrs:
					if name == 'href' and value and value.startswith('archlinux-keyring-') and value.endswith('.zst'):
						self.links.append(value)

	url = f'{DEFAULT_MIRROR}/core/os/x86_64/'
	with urllib.request.urlopen(url, timeout=30) as resp:
		content = resp.read().decode('utf-8')

	parser = LinkParser()
	parser.feed(content)

	if not parser.links:
		raise RuntimeError('Could not find archlinux-keyring package')

	# Get the latest (sorted alphabetically, newest version last)
	pkg = sorted(parser.links)[-1]
	return f'{url}{pkg}'


def _extract_zst(zst_path: Path, dest: Path) -> None:
	"""Extract a .tar.zst file."""
	# Try using zstd command
	subprocess.run(
		['zstd', '-d', '-c', str(zst_path)],
		stdout=open(dest / 'archive.tar', 'wb'),
		check=True,
	)
	with tarfile.open(dest / 'archive.tar') as tar:
		tar.extractall(dest)


def ensure_keyring_initialized() -> None:
	"""
	Ensure pacman keyring is initialized with Arch Linux keys.
	Downloads archlinux-keyring if needed (for non-Arch hosts).
	"""
	from ..output import info

	# Check if keyring already exists
	if ARCHLINUX_KEYRING.exists():
		return

	info('Setting up Arch Linux keyring...')

	# Download archlinux-keyring package
	info('Downloading archlinux-keyring...')
	pkg_url = _fetch_keyring_package_url()

	with tempfile.TemporaryDirectory() as tmpdir:
		tmppath = Path(tmpdir)
		pkg_file = tmppath / 'archlinux-keyring.pkg.tar.zst'

		urllib.request.urlretrieve(pkg_url, pkg_file)

		info('Extracting keyring...')
		_extract_zst(pkg_file, tmppath)

		# Copy keyring files to system
		KEYRING_DIR.mkdir(parents=True, exist_ok=True)
		src_keyring = tmppath / 'usr' / 'share' / 'pacman' / 'keyrings'
		for f in src_keyring.iterdir():
			shutil.copy2(f, KEYRING_DIR / f.name)

	# Initialize pacman-key
	info('Initializing pacman-key...')
	subprocess.run(['pacman-key', '--init'], check=True)
	subprocess.run(['pacman-key', '--populate', 'archlinux'], check=True)


def ensure_pacman_configured() -> None:
	"""
	Ensure pacman is configured with repos and mirrorlist.
	Needed when running from non-Arch hosts (Alpine, etc).
	"""
	from ..output import info

	if _has_repos_configured():
		return

	info('Configuring pacman for non-Arch host...')

	# Create mirrorlist
	PACMAN_D.mkdir(parents=True, exist_ok=True)
	if not MIRRORLIST.exists():
		info(f'Creating {MIRRORLIST}...')
		MIRRORLIST.write_text(DEFAULT_MIRRORS)

	# Fetch and write pacman.conf
	info(f'Writing {PACMAN_CONF}...')
	content = _fetch_pacman_conf()
	PACMAN_CONF.write_text(content)
