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
		"""Install packages to target using pyalpm instead of pacstrap."""
		import shutil

		import pyalpm

		from .hardware import SysInfo
		from .output import debug
		from .pm.mirrors import MirrorListHandler, _MirrorCache

		def _cb_log(level: int, msg: str) -> None:
			debug(f'[ALPM] {msg.strip()}')

		def _cb_progress(target: str, percent: int, n: int, i: int) -> None:
			if target and percent == 0:
				info(f'({i}/{n}) {target}')

		try:
			# Create directory structure (like pacstrap)
			for d in ['var/lib/pacman', 'var/log', 'var/cache/pacman/pkg', 'etc/pacman.d']:
				(self.target / d).mkdir(parents=True, exist_ok=True)

			# Copy GPG keyring from host (required for signature verification)
			host_gpgdir = Path('/etc/pacman.d/gnupg')
			target_gpgdir = self.target / 'etc/pacman.d/gnupg'
			if host_gpgdir.exists() and not target_gpgdir.exists():
				shutil.copytree(
					host_gpgdir,
					target_gpgdir,
					ignore=shutil.ignore_patterns('S.*'),  # Skip socket files
				)

			# Get architecture
			arch = SysInfo._arch().value.lower()

			debug(f'pyalpm Handle: root={self.target}, dbpath={self.target}/var/lib/pacman, arch={arch}')
			handle = pyalpm.Handle(str(self.target), str(self.target / 'var/lib/pacman'))
			handle.arch = [arch]  # Must be set for package installation
			handle.add_cachedir('/var/cache/pacman/pkg')
			handle.gpgdir = str(target_gpgdir)
			handle.logcb = _cb_log
			handle.progresscb = _cb_progress

			# Load mirrors and get server URLs
			MirrorListHandler().load_local_mirrors()
			mirrors = [e.server_url for entries in _MirrorCache.data.values() for e in entries]

			# Register repos with mirrors
			for repo in ['core', 'extra']:
				db = handle.register_syncdb(repo, pyalpm.SIG_DATABASE_OPTIONAL)
				db.servers = [url.replace('$repo', repo).replace('$arch', arch) for url in mirrors]
				db.update(False)

			# Resolve packages and all dependencies
			syncdbs = handle.get_syncdbs()
			resolved: dict[str, pyalpm.Package] = {}
			pending = list(packages)

			while pending:
				dep = pending.pop(0)
				if dep in resolved:
					continue

				pkg = None
				for db in syncdbs:
					if pkg := pyalpm.find_satisfier(db.pkgcache, dep):
						break

				if not pkg:
					raise RequirementError(f'Cannot satisfy dependency: {dep}')

				if pkg.name in resolved:
					continue

				resolved[pkg.name] = pkg
				pending.extend(pkg.depends)

			info(f'Resolved {len(resolved)} packages (including dependencies)')

			trans = handle.init_transaction()
			try:
				for pkg in resolved.values():
					trans.add_pkg(pkg)
				trans.prepare()

				# Debug: check what's actually in the transaction
				to_add = list(trans.to_add)
				debug(f'Transaction has {len(to_add)} packages to install')

				trans.commit()

				# Verify installation
				osrelease = self.target / 'etc/os-release'
				if osrelease.exists():
					info('Base system installed successfully')
				else:
					warn(f'Warning: {osrelease} not found after install!')
					debug(f'Target contents: {list((self.target / "etc").iterdir()) if (self.target / "etc").exists() else "etc dir missing"}')

			finally:
				trans.release()

		except pyalpm.error as e:
			raise RequirementError(f'ALPM error: {e}')
