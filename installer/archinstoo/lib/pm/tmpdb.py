# Private pacman DBPath, as checkupdates (pacman-contrib) does it. Its own
# pacman.conf holds only the asked repos: extra.files alone is ~50 MB

import os
import subprocess
import tempfile
from pathlib import Path

from archinstoo.lib.output import debug
from archinstoo.lib.utils.env import is_root

TMPDB_ROOT = Path(tempfile.gettempdir()) / f'archinstoo-db-{os.getuid()}'

# Arch's pacman.conf value; the compiled default refuses the unsigned files db
_DEFAULT_SIGLEVEL = ['Required', 'DatabaseOptional']


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
	try:
		return subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603 - fixed argv, no user input
	except OSError as err:
		return subprocess.CompletedProcess(argv, 127, '', str(err))


def _conf_values(key: str, repo: str | None = None) -> list[str]:
	scope = [f'--repo={repo}'] if repo else []
	proc = _run(['pacman-conf', *scope, key])
	return proc.stdout.split() if proc.returncode == 0 else []


def render_conf(siglevel: list[str], servers: dict[str, list[str]]) -> str:
	lines = ['[options]', 'Architecture = auto', f'SigLevel = {" ".join(siglevel or _DEFAULT_SIGLEVEL)}']
	for repo, urls in servers.items():
		lines += ['', f'[{repo}]', *(f'Server = {url}' for url in urls)]
	return '\n'.join(lines) + '\n'


def parse_files(text: str) -> list[tuple[str, str]]:
	pairs: list[tuple[str, str]] = []
	for line in text.splitlines():
		pkg, _, path = line.partition(' ')
		if path and not path.endswith('/'):
			pairs.append((pkg, path))
	return pairs


class TmpDB:
	def __init__(self, repos: tuple[str, ...], root: Path = TMPDB_ROOT) -> None:
		self.repos = repos
		self.root = root
		self.conf = root / 'pacman.conf'

	def _pacman(self, *args: str) -> list[str]:
		return ['pacman', '--config', str(self.conf), '--dbpath', str(self.root), '--logfile', '/dev/null', *args]

	def sync_files(self) -> bool:
		servers = {repo: _conf_values('Server', repo) for repo in self.repos}
		if missing := [repo for repo, urls in servers.items() if not urls]:
			debug(f'tmpdb: no servers for {missing} in pacman.conf')
			return False

		self.root.mkdir(parents=True, exist_ok=True)
		self.conf.write_text(render_conf(_conf_values('SigLevel'), servers))

		# -y needs root even on a private dbpath; the ISO ships no fakeroot
		argv = self._pacman('--disable-sandbox-filesystem', '-Fy')
		try:
			proc = _run(argv if is_root() else ['fakeroot', '--', *argv])
		finally:
			# a killed pacman leaves its lock behind
			(self.root / 'db.lck').unlink(missing_ok=True)

		if proc.returncode != 0:
			debug(f'tmpdb: files sync of {self.repos} failed: {proc.stderr.strip()}')
			return False
		return True

	def files(self) -> list[tuple[str, str]]:
		proc = _run(self._pacman('-Fl'))
		if proc.returncode != 0:
			debug(f'tmpdb: listing {self.repos} failed: {proc.stderr.strip()}')
			return []
		return parse_files(proc.stdout)
