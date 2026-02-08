import contextlib
import time
from collections.abc import Callable
from pathlib import Path

from .exceptions import RequirementError
from .general import SysCommand
from .output import error, info, logger, warn
from .translationhandler import tr


# Helpers for exceptions
def reset_conf() -> bool:
	# reset pacman.conf to upstream default in case a modification is causing breakage
	try:
		default_pm_conf = 'https://gitlab.archlinux.org/archlinux/packaging/packages/pacman/-/raw/main/pacman.conf'
		info('Fetching default pacman.conf from upstream...')
		from .network.utils import fetch_data_from_url

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
		"""
		A centralized function to call `pacman` from.
		It also protects us from colliding with other running pacman sessions (if used locally).
		The grace period is set to 10 minutes before exiting hard if another pacman instance is running.
		"""
		pacman_db_lock = Path('/var/lib/pacman/db.lck')

		if pacman_db_lock.exists():
			warn(tr('Pacman is already running, waiting maximum 10 minutes for it to terminate.'))

		started = time.time()
		while pacman_db_lock.exists():
			time.sleep(0.25)

			if time.time() - started > (60 * 10):
				error(tr('Pre-existing pacman lock never exited. Please clean up any existing pacman sessions before using archinstoo.'))
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
				SysCommand('umount -l /etc/pacman.d/gnupg', peek_output=True)
			with contextlib.suppress(Exception):
				SysCommand('rm -rf /etc/pacman.d/gnupg', peek_output=True)
			Pacman.run('--init', default_cmd='pacman-key', peek_output=True)
			Pacman.run('--populate archlinux', default_cmd='pacman-key', peek_output=True)
			Pacman.run('-Sy archlinux-keyring', peek_output=True)
			info('Pacman keyring reinitialized.')
			return True
		except Exception as e:
			error(f'Keyring reset failed: {e}')
			return False

	def ask(self, error_message: str, bail_message: str, func: Callable, *args, **kwargs) -> None:  # type: ignore[no-untyped-def, type-arg]
		try:
			func(*args, **kwargs)
		except Exception as err:
			err_str = str(err).lower()
			error(f'{error_message}: {err}')

			recovery = None
			if 'invalid or corrupted package' in err_str:
				warn('Detected corrupted package: resetting keyring and retrying...')
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
			self.ask(
				'Could not strap in packages',
				bail,
				SysCommand,
				cmd,
				peek_output=True,
			)
		else:
			self._strap_pyalpm(packages)

	def _strap_pyalpm(self, packages: list[str]) -> None:
		"""Install packages to target using pyalpm."""
		import pyalpm

		from .hardware import SysInfo
		from .output import debug
		from .pm.mirrors import MirrorListHandler, _MirrorCache

		_last: list[str] = ['']

		def log_cb(level: int, msg: str) -> None:
			debug(f'[ALPM] {msg.strip()}')

		def event_cb(event: str, data: tuple) -> None:  # type: ignore[type-arg]
			debug(f'[EVENT] {event}: {data}')

		def question_cb(*args: object) -> int:
			debug(f'[QUESTION] {args}')
			return 1  # auto-accept

		def progress_cb(target: str, percent: int, n: int, i: int) -> None:
			if target and percent == 0 and target != _last[0]:
				_last[0] = target
				info(f'({i}/{n}) Installing {target}')

		# Setup target directories
		for d in ['var/lib/pacman', 'var/cache/pacman/pkg', 'etc/pacman.d']:
			(self.target / d).mkdir(parents=True, exist_ok=True)

		# Initialize keyring in target (like pacstrap -K)
		dst_gpg = self.target / 'etc/pacman.d/gnupg'
		if not dst_gpg.exists():
			SysCommand(f'pacman-key --gpgdir {dst_gpg} --init', peek_output=True)
			SysCommand(f'pacman-key --gpgdir {dst_gpg} --populate archlinux', peek_output=True)

		arch = SysInfo._arch().value.lower()
		root = str(self.target.resolve())
		dbpath = str((self.target / 'var/lib/pacman').resolve())

		info(f'pyalpm: root={root}, arch={arch}')

		# Create handle
		h = pyalpm.Handle(root, dbpath)
		h.arch = [arch]
		h.gpgdir = str(dst_gpg)
		h.add_cachedir('/var/cache/pacman/pkg')
		h.logcb = log_cb
		h.eventcb = event_cb
		h.questioncb = question_cb
		h.progresscb = progress_cb

		# Load mirrors
		MirrorListHandler().load_local_mirrors()
		mirrors = [e.server_url for entries in _MirrorCache.data.values() for e in entries]

		# Register sync dbs
		for repo in ['core', 'extra']:
			db = h.register_syncdb(repo, pyalpm.SIG_DATABASE_OPTIONAL)
			db.servers = [m.replace('$repo', repo).replace('$arch', arch) for m in mirrors]
			db.update(False)

		# Resolve all deps
		syncdbs = h.get_syncdbs()
		resolved: dict[str, pyalpm.Package] = {}
		queue = list(packages)

		while queue:
			name = queue.pop(0)
			if name in resolved:
				continue
			for db in syncdbs:
				if pkg := pyalpm.find_satisfier(db.pkgcache, name):
					if pkg.name not in resolved:
						resolved[pkg.name] = pkg
						queue.extend(pkg.depends)
					break
			else:
				raise RequirementError(f'Package not found: {name}')

		info(f'Resolved {len(resolved)} packages')

		# Transaction
		t = h.init_transaction()
		try:
			for pkg in resolved.values():
				t.add_pkg(pkg)
			t.prepare()
			info(f'Installing {len(list(t.to_add))} packages...')
			t.commit()
		finally:
			t.release()
