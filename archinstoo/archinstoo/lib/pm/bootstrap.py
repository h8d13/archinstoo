from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from archinstoo.lib.output import info

_PACMAN_CONF = Path('/etc/pacman.conf')
_PACMAN_D = Path('/etc/pacman.d')
_MIRRORLIST = _PACMAN_D / 'mirrorlist'
_KEYRING_DIR = Path('/usr/share/pacman/keyrings')
_ARCHLINUX_KEYRING = _KEYRING_DIR / 'archlinux.gpg'

_MIRROR_STATUS_URL = 'https://archlinux.org/mirrors/status/json/'


def _fetch_mirrorlist() -> str:

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

	# Remove DownloadUser — the alpm user won't exist on non-Arch hosts
	content = re.sub(r'^DownloadUser\s*=.*\n', '', content, flags=re.MULTILINE)
	return content


def _fetch_keyring_package_url() -> str:
	"""Find the latest archlinux-keyring package URL from the geo mirror."""
	url = 'https://geo.mirror.pkgbuild.com/core/os/x86_64/'
	with urllib.request.urlopen(url, timeout=30) as resp:
		content = resp.read().decode('utf-8')

	links = re.findall(r'href="(archlinux-keyring-[^"]+\.zst)"', content)
	if not links:
		raise RuntimeError('Could not find archlinux-keyring package on mirror')

	return f'{url}{sorted(links)[-1]}'


def _extract_zst(zst_path: Path, dest: Path) -> None:
	"""Decompress a .tar.zst archive into dest."""
	subprocess.run(['tar', '--zstd', '-xf', str(zst_path), '-C', str(dest)], check=True)


def keyring_init() -> None:
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


def pacman_conf() -> None:
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
