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
		import traceback

		import pyalpm

		from .hardware import SysInfo
		from .output import debug
		from .pm.mirrors import MirrorListHandler, _MirrorCache

		_last_pkg: list[str] = ['']

		def _cb_log(level: int, msg: str) -> None:
			debug(f'[ALPM] {msg.strip()}')

		def _cb_dl(filename: str, tx: int, total: int) -> None:
			if filename != _last_pkg[0]:
				_last_pkg[0] = filename
				info(f':: Downloading {filename}')

		def _cb_progress(target: str, percent: int, n: int, i: int) -> None:
			key = f'{i}/{n}/{target}'
			if target and percent == 0 and key != _last_pkg[0]:
				_last_pkg[0] = key
				info(f'({i}/{n}) Installing {target}')

		def _cb_event(event: str, data: tuple) -> None:  # type: ignore[type-arg]
			# Event callback for package operations
			debug(f'[ALPM EVENT] {event}: {data}')

		def _cb_question(*args: object) -> int:
			# Question callback - auto-accept for non-interactive install
			debug(f'[ALPM QUESTION] {args}')
			return 1  # Accept

		try:
			# Create directory structure (like pacstrap)
			# Include all directories pacstrap creates
			for d in [
				'var/lib/pacman',
				'var/lib/pacman/local',
				'var/log',
				'var/cache/pacman/pkg',
				'etc/pacman.d',
				'run',
				'tmp',
			]:
				(self.target / d).mkdir(parents=True, exist_ok=True)

			# Set proper permissions on tmp
			(self.target / 'tmp').chmod(0o1777)

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

			# Ensure absolute paths
			root_path = str(self.target.resolve())
			db_path = str((self.target / 'var/lib/pacman').resolve())

			debug(f'pyalpm Handle: root={root_path}, dbpath={db_path}, arch={arch}')
			info(f'Installing to: {root_path}')

			handle = pyalpm.Handle(root_path, db_path)

			# Verify the handle was created with correct root
			debug(f'Handle root: {handle.root}, dbpath: {handle.dbpath}')
			handle.arch = [arch]  # Must be set for package installation

			# Add cache directories - both host and target
			handle.add_cachedir('/var/cache/pacman/pkg')
			handle.add_cachedir(str(self.target / 'var/cache/pacman/pkg'))

			handle.gpgdir = str(target_gpgdir)

			# Set all callbacks
			handle.logcb = _cb_log
			handle.dlcb = _cb_dl
			handle.progresscb = _cb_progress
			handle.eventcb = _cb_event
			handle.questioncb = _cb_question

			# Initialize local database (important!)
			localdb = handle.get_localdb()
			debug(f'Local DB initialized: {localdb.name}')

			# Load mirrors and get server URLs
			MirrorListHandler().load_local_mirrors()
			mirrors = [e.server_url for entries in _MirrorCache.data.values() for e in entries]
			debug(f'Loaded {len(mirrors)} mirror URLs')

			if not mirrors:
				raise RequirementError('No mirrors available for package installation')

			# Register repos with mirrors
			for repo in ['core', 'extra']:
				db = handle.register_syncdb(repo, pyalpm.SIG_DATABASE_OPTIONAL)
				db.servers = [url.replace('$repo', repo).replace('$arch', arch) for url in mirrors]
				debug(f'Registered {repo} with {len(db.servers)} servers')
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

			# Initialize transaction with flags for bootstrap install
			trans = handle.init_transaction(
				nodeps=False,
				force=False,
				nosave=False,
				nodepversion=False,
				cascade=False,
				recurse=False,
				dbonly=False,
				downloadonly=False,
				noscriptlet=False,
				needed=False,
			)

			try:
				for pkg in resolved.values():
					trans.add_pkg(pkg)

				# Prepare - check for errors
				debug('Preparing transaction...')
				try:
					trans.prepare()
				except pyalpm.error as prep_err:
					error(f'Transaction prepare failed: {prep_err}')
					traceback.print_exc()
					raise RequirementError(f'Transaction prepare failed: {prep_err}')

				# Debug: check what's actually in the transaction
				to_add = list(trans.to_add)
				to_remove = list(trans.to_remove)
				debug(f'Transaction: {len(to_add)} to install, {len(to_remove)} to remove')

				if not to_add:
					warn('Transaction has no packages to install!')
					raise RequirementError('Transaction has no packages to install')

				# Commit - actually install
				debug('Committing transaction...')
				try:
					trans.commit()
					debug('Transaction committed successfully')
				except pyalpm.error as commit_err:
					error(f'Transaction commit failed: {commit_err}')
					traceback.print_exc()
					raise RequirementError(f'Transaction commit failed: {commit_err}')

				# Verify installation
				osrelease = self.target / 'etc/os-release'
				if osrelease.exists():
					info('Base system installed successfully')
				else:
					warn(f'Warning: {osrelease} not found after install!')
					# List what was created
					etc_dir = self.target / 'etc'
					if etc_dir.exists():
						debug(f'Target /etc contents: {list(etc_dir.iterdir())[:20]}')
					else:
						debug('Target /etc does not exist!')

					# Check if any files were installed
					usr_dir = self.target / 'usr'
					if usr_dir.exists():
						debug(f'Target /usr exists with: {list(usr_dir.iterdir())[:10]}')
					else:
						debug('Target /usr does not exist - packages NOT extracted!')

			finally:
				trans.release()

		except pyalpm.error as e:
			error(f'ALPM error: {e}')
			traceback.print_exc()
			raise RequirementError(f'ALPM error: {e}')
