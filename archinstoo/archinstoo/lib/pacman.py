import contextlib
import os
import signal
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .exceptions import RequirementError
from .general import SysCommand
from .output import error, info, logger, warn
from .pathnames import PACMAN_CONF

if TYPE_CHECKING:
	from collections.abc import Callable


def _target_gpg_daemons(target: Path) -> list[int]:
	# gnupg's post_install runs `dirmngr </dev/null`, which can leave a dirmngr/
	# gpg-agent daemon holding libalpm's scriptlet pipe open; pacstrap then blocks
	# at the gnupg step waiting for an EOF that never comes (FS#42798). The legit
	# package-verify agent runs host-rooted (/), so only the chrooted scriptlet
	# daemon resolves /proc/<pid>/root to the target. Match exactly those.
	root = os.path.realpath(target)
	pids: list[int] = []
	for entry in Path('/proc').iterdir():
		if not entry.name.isdigit():
			continue
		try:
			comm = (entry / 'comm').read_text().strip()
			if comm not in ('dirmngr', 'gpg-agent'):
				continue
			if os.path.realpath(entry / 'root') == root:
				pids.append(int(entry.name))
		except OSError:
			continue  # pid vanished or unreadable mid-scan
	return pids


def _scriptlet_watchdog(target: Path, stop: threading.Event) -> None:
	# Reap leaked gnupg scriptlet daemons (see _target_gpg_daemons) once they
	# outlive a grace window, so a held pipe can't wedge pacstrap. On hosts that
	# don't hang the daemon exits in <1s and we never fire: a no-op there.
	grace = 8.0
	seen: dict[int, float] = {}
	while not stop.wait(2.0):
		pids = _target_gpg_daemons(target)
		now = time.monotonic()
		for pid in pids:
			if now - seen.setdefault(pid, now) > grace:
				warn(f'Reaping stuck gnupg scriptlet daemon (pid {pid}) in target...')
				with contextlib.suppress(ProcessLookupError):
					os.kill(pid, signal.SIGTERM)
		seen = {p: t for p, t in seen.items() if p in pids}


# Helpers for exceptions
def reset_conf() -> bool:
	# reset pacman.conf to upstream default in case a modification is causing breakage
	try:
		default_pm_conf = 'https://gitlab.archlinux.org/archlinux/packaging/packages/pacman/-/raw/main/pacman.conf'
		info('Fetching default pacman.conf from upstream...')
		from .utils.net import fetch_data_from_url

		conf_data = fetch_data_from_url(default_pm_conf)
		Path('/etc/pacman.conf').write_text(conf_data)
		info('Replaced /etc/pacman.conf with upstream default.')
		return True
	except Exception as e:
		error(f'Config reset failed: {e}')
		return False


class Pacman:
	def __init__(self, target: Path):
		self.synced = False
		self.target = target

	@staticmethod
	def run(args: str, default_cmd: str = 'pacman', peek_output: bool = False) -> SysCommand:
		# A centralized function to call `pacman` from.
		# It also protects us from colliding with other running pacman sessions (if used locally).
		# The grace period is set to 10 minutes before exiting hard if another pacman instance is running.
		pacman_db_lock = Path('/var/lib/pacman/db.lck')

		if pacman_db_lock.exists():
			warn('Pacman is already running, waiting maximum 10 minutes for it to terminate.')

		started = time.monotonic()
		while pacman_db_lock.exists():
			time.sleep(0.25)

			if time.monotonic() - started > (60 * 10):
				error('Pre-existing pacman lock never exited. Please clean up any existing pacman sessions before using archinstoo.')
				raise SystemExit(1)

		return SysCommand(f'{default_cmd} {args}', peek_output=peek_output)

	@staticmethod
	def reset_keyring() -> bool:
		# reset keyring in case of corrupted packages
		try:
			info('Reinitializing pacman keyring...')
			with contextlib.suppress(Exception):
				SysCommand('killall gpg-agent', peek_output=True)
			with contextlib.suppress(Exception):
				SysCommand('rm -rf /etc/pacman.d/gnupg', peek_output=True)
			Pacman.run('--init', default_cmd='pacman-key', peek_output=True)
			Pacman.run('--populate archlinux', default_cmd='pacman-key', peek_output=True)
			Pacman.run('-Sy archlinux-keyring --noconfirm', peek_output=True)
			info('Pacman keyring reinitialized.')
			return True
		except Exception as e:
			error(f'Keyring reset failed: {e}')
			return False

	def ask(self, error_message: str, bail_message: str, func: Callable[..., object], *args: object, **kwargs: object) -> None:
		try:
			func(*args, **kwargs)
		except Exception as err:
			err_str = str(err).lower()
			error(f'{error_message}: {err}')

			recovery = None
			if 'invalid or corrupted package' in err_str:
				warn('Detected corrupted package: resetting keyring and retrying...')
				recovery = Pacman.reset_keyring
			elif 'gpgme error' in err_str or 'no data' in err_str or 'signature' in err_str:
				warn('Detected keyring/signature issue: resetting keyring and retrying...')
				recovery = Pacman.reset_keyring
			elif 'could not satisfy dependencies' in err_str:
				warn('Detected dependency issue: resetting pacman.conf and retrying...')
				recovery = reset_conf

			if recovery and recovery():
				try:
					func(*args, **kwargs)
					return
				except Exception as retry_err:
					raise RequirementError(f'{bail_message}: {retry_err}')

			if input('Would you like to re-try this download? (Y/n): ').lower().strip() in ('', 'y'):
				try:
					func(*args, **kwargs)
					return
				except Exception as retry_err:
					raise RequirementError(f'{bail_message}: {retry_err}')

			raise RequirementError(f'{bail_message}: {err}')

	def sync(self) -> None:
		if self.synced:
			return
		self.ask(
			'Could not sync a new package database',
			'Could not sync mirrors',
			self.run,
			'-Syy',
			default_cmd='pacman',
		)
		self.synced = True

	def strap(self, packages: str | list[str]) -> None:
		self.sync()
		if isinstance(packages, str):
			packages = [packages]

		info(f'Installing packages: {packages}')

		if self.target == Path('/'):
			# Live mode: install directly on the running system
			cmd = f'pacman -S {" ".join(packages)} --noconfirm --needed'
			bail = f'Package installation failed. See {logger.path} or above message for error details'
		else:
			# no -K: that builds an empty target keyring and re-signs every arch
			# key from scratch (slow, entropy-bound, storms gpg on fresh hosts).
			# keyring_init() already populated the host keyring, so let pacstrap
			# copy it into the target (its default when -K/-G are absent).
			cmd = f'pacstrap -C {PACMAN_CONF} {self.target} {" ".join(packages)} --noconfirm --needed'
			bail = f'Pacstrap failed. See {logger.path} or above message for error details'

		# Only chrooted installs run package scriptlets; live mode (target '/')
		# shares the host gpg, where a root match would catch the wrong daemon.
		stop = watchdog = None
		if self.target != Path('/'):
			stop = threading.Event()
			watchdog = threading.Thread(target=_scriptlet_watchdog, args=(self.target, stop), daemon=True)
			watchdog.start()

		try:
			self.ask(
				'Could not strap in packages',
				bail,
				SysCommand,
				cmd,
				peek_output=True,
			)
		finally:
			if stop is not None and watchdog is not None:
				stop.set()
				watchdog.join(timeout=2)
