import importlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from shutil import rmtree, which

from archinstoo.lib.exceptions import RequirementError
from archinstoo.lib.output import error, info


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

	@staticmethod
	def running_from_host() -> bool:
		# returns True when not on the ISO
		return not Path('/run/archiso').exists()

	@staticmethod
	def running_from_who() -> str:
		# checks distro name
		if os.path.exists('/etc/os-release'):
			with open('/etc/os-release') as f:
				for line in f:
					if line.startswith('ID='):
						return line.strip().split('=')[1]
		return ''

	@staticmethod
	def running_from_arch() -> bool:
		# confirm its arch host
		return Os.running_from_who() == 'arch'

	# match Os.running_from_who():
	# case 'alpine':
	# do something else

	@staticmethod
	def locate_binary(name: str) -> str:
		if path := which(name):
			return path
		raise RequirementError(f'Binary {name} does not exist.')

	# to avoid using shutil.which everywhere


def is_venv() -> bool:
	return sys.prefix != getattr(sys, 'base_prefix', sys.prefix)


def _run_script(script: str) -> None:
	try:
		# by importing we automatically run it
		importlib.import_module(f'archinstoo.scripts.{script}')
	except ModuleNotFoundError as e:
		# Only catch if the missing module is the script itself
		if f'archinstoo.scripts.{script}' in str(e):
			error(f'Script: {script} does not exist. Try `--script list` to see your options.')
			raise SystemExit(1)


def reload_python() -> None:
	# dirty python trick to reload any changed library modules
	# skip reload during testing
	if 'pytest' in sys.modules:
		return
	os.execv(sys.executable, [sys.executable, '-m', 'archinstoo'] + sys.argv[1:])


def is_root() -> bool:
	return os.getuid() == 0


def kernel_info() -> str:
	return f'{platform.release()} built {platform.version()}'


_PACMAN_CONF = Path('/etc/pacman.conf')
_PACMAN_D = Path('/etc/pacman.d')
_MIRRORLIST = _PACMAN_D / 'mirrorlist'
_KEYRING_DIR = Path('/usr/share/pacman/keyrings')
_ARCHLINUX_KEYRING = _KEYRING_DIR / 'archlinux.gpg'

_MIRROR_STATUS_URL = 'https://archlinux.org/mirrors/status/json/'


def _fetch_mirrorlist() -> str:
	import json

	info(f'Fetching mirrorlist from {_MIRROR_STATUS_URL}...')
	with urllib.request.urlopen(_MIRROR_STATUS_URL, timeout=15) as resp:
		data = json.loads(resp.read().decode('utf-8'))
	lines = ['# Arch Linux mirrors fetched by archinstoo bootstrap']
	lines.extend(
		f'Server = {mirror["url"]}$repo/os/$arch'
		for mirror in data.get('urls', [])
		if mirror.get('active') and mirror.get('protocol') in ('https', 'http') and mirror.get('score') is not None and mirror['score'] < 100
	)
	return '\n'.join(lines) + '\n'


_PACMAN_CONF_URL = 'https://gitlab.archlinux.org/archlinux/packaging/packages/pacman/-/raw/main/pacman.conf'


def _has_repos_configured() -> bool:
	"""Return True if pacman.conf already has at least one enabled repo section."""
	if not _PACMAN_CONF.exists():
		return False
	content = _PACMAN_CONF.read_text()
	# Match uncommented [section] lines that are not [options]
	return bool(re.search(r'^\[(?!options\b)[\w-]+\]', content, re.MULTILINE))


def _fetch_pacman_conf() -> str:
	"""Fetch the upstream pacman.conf and relax it for non-Arch bootstrap use."""
	info(f'Fetching pacman.conf from {_PACMAN_CONF_URL}...')
	with urllib.request.urlopen(_PACMAN_CONF_URL, timeout=30) as resp:
		content = resp.read().decode('utf-8')

	# Relax signature checking — the keyring may not be set up yet
	content = re.sub(r'^SigLevel\s*=.*$', 'SigLevel = Never', content, flags=re.MULTILINE)
	# Remove DownloadUser — the alpm user won't exist on non-Arch hosts
	content = re.sub(r'^DownloadUser\s*=.*\n', '', content, flags=re.MULTILINE)
	return content


def _fetch_keyring_package_url() -> str:
	"""Find the latest archlinux-keyring package URL from the geo mirror."""
	import html.parser
	from typing import override

	class _LinkParser(html.parser.HTMLParser):
		def __init__(self) -> None:
			super().__init__()
			self.links: list[str] = []

		@override
		def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
			if tag == 'a':
				for name, value in attrs:
					if name == 'href' and value and value.startswith('archlinux-keyring-') and value.endswith('.zst'):
						self.links.append(value)

	url = 'https://geo.mirror.pkgbuild.com/core/os/x86_64/'
	with urllib.request.urlopen(url, timeout=30) as resp:
		content = resp.read().decode('utf-8')

	parser = _LinkParser()
	parser.feed(content)

	if not parser.links:
		raise RuntimeError('Could not find archlinux-keyring package on mirror')

	pkg = sorted(parser.links)[-1]  # latest version sorts last alphabetically
	return f'{url}{pkg}'


def _extract_zst(zst_path: Path, dest: Path) -> None:
	"""Decompress a .tar.zst archive into dest."""
	tar_path = dest / 'archive.tar'
	with open(tar_path, 'wb') as tar_out:
		subprocess.run(['zstd', '-d', '-c', str(zst_path)], stdout=tar_out, check=True)
	with tarfile.open(tar_path) as tar:
		tar.extractall(dest)


def ensure_keyring_initialized() -> None:
	"""
	Ensure the Arch Linux pacman keyring is present.
	Downloads and extracts archlinux-keyring when running from a non-Arch host.
	No-op if the keyring is already installed.
	"""
	if _ARCHLINUX_KEYRING.exists():
		return

	info('Setting up Arch Linux keyring (non-Arch host)...')

	pkg_url = _fetch_keyring_package_url()
	with tempfile.TemporaryDirectory() as tmp:
		tmpdir = Path(tmp)
		pkg_file = tmpdir / 'archlinux-keyring.pkg.tar.zst'
		info(f'Downloading {pkg_url}...')
		urllib.request.urlretrieve(pkg_url, pkg_file)

		info('Extracting keyring...')
		_extract_zst(pkg_file, tmpdir)

		_KEYRING_DIR.mkdir(parents=True, exist_ok=True)
		src = tmpdir / 'usr' / 'share' / 'pacman' / 'keyrings'
		for f in src.iterdir():
			shutil.copy2(f, _KEYRING_DIR / f.name)

	info('Initializing pacman-key...')
	subprocess.run(['pacman-key', '--init'], check=True)
	subprocess.run(['pacman-key', '--populate', 'archlinux'], check=True)


def ensure_pacman_configured() -> None:
	"""
	Ensure pacman has a working mirrorlist and repo configuration.
	Needed when running from a non-Arch host (Alpine, Debian, Fedora, …).
	No-op if repos are already configured.
	"""
	if _has_repos_configured():
		return

	info('Configuring pacman for non-Arch host...')

	_PACMAN_D.mkdir(parents=True, exist_ok=True)
	info(f'Writing {_MIRRORLIST}...')
	_MIRRORLIST.write_text(_fetch_mirrorlist())

	info(f'Writing {_PACMAN_CONF}...')
	_PACMAN_CONF.write_text(_fetch_pacman_conf())


def clean_cache(root_dir: str) -> None:
	# only clean if running from source (archinstoo dir exists in cwd)
	if not os.path.isdir(os.path.join(root_dir, 'archinstoo')):
		return

	deleted = []

	info('Cleaning up...')
	try:
		for dirpath, dirnames, _ in os.walk(root_dir):
			for dirname in dirnames:
				if dirname.lower() == '__pycache__':
					full_path = os.path.join(dirpath, dirname)
					try:
						rmtree(full_path)
						deleted.append(full_path)
					except Exception as e:
						info(f'Failed to delete {full_path}: {e}')
	except PermissionError:
		pass

	if deleted:
		info(f'Done. {len(deleted)} cache folder(s) deleted.')
