import contextlib
import re
import shutil
import sys
import tempfile
import termios
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Final

from archinstoo.lib.chroot import drop_to_shell
from archinstoo.lib.exceptions import RequirementError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.linux_path import LPath
from archinstoo.lib.output import debug, error, info, logger, warn
from archinstoo.lib.utils.host import Host

if TYPE_CHECKING:
	from collections.abc import Callable

# pacman's own files on the running system; under a target, relative_to_root()
PACMAN_CONF: Final = LPath('/etc/pacman.conf')
PACMAN_GNUPG: Final = LPath('/etc/pacman.d/gnupg')
MIRRORLIST: Final = LPath('/etc/pacman.d/mirrorlist')
PACMAN_DB: Final = LPath('/var/lib/pacman')


@cache
def _workdir() -> tempfile.TemporaryDirectory[str]:
	# this run's private pacman state; cached so it is made once, its
	# finalizer removes it at exit. On an Arch host '/' is the user's own
	# system: conf and mirrorlist are copied in and a sync db made, so menu
	# edits and -Sy never reach /etc or /var/lib/pacman. The ISO and the
	# bootstrap root are thrown away, so they use those directly.
	tmp = tempfile.TemporaryDirectory(prefix='archinstoo-pm-')
	if not Host.running_from_arch_host():
		return tmp

	root = Path(tmp.name)
	(root / PACMAN_DB.name).mkdir()
	mirrorlist = MIRRORLIST.copy(root / MIRRORLIST.name)
	# only the Arch mirrorlist moves, third-party Includes keep reading /etc
	conf = re.sub(
		rf'^([ \t]*Include[ \t]*=[ \t]*){re.escape(str(MIRRORLIST))}[ \t]*$',
		rf'\g<1>{mirrorlist}',
		PACMAN_CONF.read_text(),
		flags=re.MULTILINE,
	)
	(root / PACMAN_CONF.name).write_text(conf)
	debug(f'Host pacman.conf and mirrorlist copied to {root}')
	return tmp


def workdir() -> Path:
	return Path(_workdir().name)


def live(path: LPath) -> LPath:
	# what this run reads and writes for PACMAN_CONF, MIRRORLIST or PACMAN_DB
	if not Host.running_from_arch_host():
		return path
	return LPath(workdir()) / path.name


# Helpers for exceptions
def reset_conf() -> bool:
	# reset pacman.conf to upstream default in case a
	# modification is causing breakage
	try:
		default_pm_conf = 'https://gitlab.archlinux.org/archlinux/packaging/packages/pacman/-/raw/main/pacman.conf'
		info('Fetching default pacman.conf from upstream...')
		from archinstoo.lib.utils.net import fetch_data_from_url

		conf_data = fetch_data_from_url(default_pm_conf)
		conf = live(PACMAN_CONF)
		conf.write_text(conf_data)
		info(f'Replaced {conf} with upstream default.')
		return True
	except Exception as e:
		error(f'Config reset failed: {e}')
		return False


# SysCommand runs under a pty, so pacman draws progress bars even
# unattended: hundreds of redraw lines per package in a --silent log.
# argv peek at import: _prepare() syncs before argparse (same as --offline),
# and pass_args_to_subscript() strips parsed flags from sys.argv afterwards.
_SILENT: Final = '--silent' in sys.argv
_QUIET_FLAGS = ' --noprogressbar' if _SILENT else ''


def _auto_recovery(err: Exception) -> Callable[[], bool] | None:
	# the tail str(err) keeps is enough: pacman ends a failed transaction
	# with the line naming its cause
	out = str(err).lower()

	if 'invalid or corrupted package' in out:
		warn('Detected corrupted package: resetting keyring...')
		return Pacman.reset_keyring
	if any(s in out for s in ('gpgme error', 'no data', 'signature')):
		warn('Detected keyring/signature issue: resetting keyring...')
		return Pacman.reset_keyring
	if 'could not satisfy dependencies' in out:
		warn('Detected dependency issue: resetting pacman.conf...')
		return reset_conf
	return None


def _can_prompt() -> bool:
	try:
		return sys.stdin.isatty()
	except AttributeError, OSError, ValueError:
		return False


def _choose() -> str:
	# keys pressed while pacstrap ran (an impatient Enter) would otherwise
	# answer unseen
	with contextlib.suppress(OSError, ValueError, termios.error):
		termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
	while True:
		try:
			answer = input('[R]etry, open a [s]hell to fix it, or [e]xit? ')
		except EOFError:
			return 'exit'
		match answer.strip().lower():
			case '' | 'r' | 'retry':
				return 'retry'
			case 's' | 'shell':
				return 'shell'
			case 'e' | 'exit':
				return 'exit'
			case _:
				pass


class Pacman:
	def __init__(self, target: Path) -> None:
		self.target = target

	@staticmethod
	def run(
		args: str, default_cmd: str = 'pacman', peek_output: bool = False
	) -> SysCommand:
		# -T and the -Q family draw no progress bar and reject the flag with
		# 'invalid option', which under --silent turned every dependency
		# check into a failed call
		if default_cmd == 'pacman' and not args.startswith(('-T', '-Q')):
			args += _QUIET_FLAGS
		if default_cmd == 'pacman':
			args = f'--config {live(PACMAN_CONF)} {args}'

		return SysCommand(f'{default_cmd} {args}', peek_output=peek_output)

	@staticmethod
	def reset_keyring() -> bool:
		# reset keyring in case of corrupted packages
		if Host.running_from_arch_host():
			# the user's own keyring: local signatures (third-party repo
			# keys) would be lost, and killall reaches their gpg-agents too
			warn(
				'Not resetting the host keyring. Update it first: '
				'pacman -Syu archlinux-keyring'
			)
			return False
		try:
			info('Reinitializing pacman keyring...')
			with contextlib.suppress(Exception):
				SysCommand('killall gpg-agent', peek_output=True)
			if PACMAN_GNUPG.exists():
				debug(f'Removing {PACMAN_GNUPG} before keyring re-init')
				try:
					shutil.rmtree(PACMAN_GNUPG)
				except OSError as e:
					warn(f'Could not remove {PACMAN_GNUPG}: {e}')
			Pacman.run('--init', default_cmd='pacman-key', peek_output=True)
			Pacman.run(
				'--populate archlinux',
				default_cmd='pacman-key',
				peek_output=True,
			)
			Pacman.run(
				'-Sy archlinux-keyring --noconfirm', peek_output=True
			)
			info('Pacman keyring reinitialized.')
			return True
		except Exception as e:
			error(f'Keyring reset failed: {e}')
			return False

	def ask(
		self,
		error_message: str,
		bail_message: str,
		func: Callable[..., object],
		*args: object,
		**kwargs: object,
	) -> None:
		def attempt() -> Exception | None:
			try:
				func(*args, **kwargs)
			except Exception as err:
				error(f'{error_message}: {err}')
				return err
			return None

		if not (err := attempt()):
			return
		recovery = _auto_recovery(err)
		if recovery and recovery() and not (err := attempt()):
			return
		while not _SILENT and _can_prompt():
			choice = _choose()
			if choice == 'exit':
				break
			if choice == 'shell':
				self._shell()
			if (retry_err := attempt()) is None:
				return
			err = retry_err
		raise RequirementError(f'{bail_message}: {err}') from err

	def _shell(self) -> None:
		if self.target == Path('/'):
			# the running system: arch-chroot / would remount /proc, /dev
			info('Fix it with pacman from another terminal, then retry.')
			return
		info("Chrooting into the target, 'exit' or Ctrl+D retries")
		drop_to_shell(self.target)

	def strap(self, packages: str | list[str]) -> None:
		# no -Sy here: pacstrap syncs the target's own db, and '/' installs
		# against the db _prepare synced (ISO) or the user keeps (Arch host)
		if isinstance(packages, str):
			packages = [packages]

		# nothing asked (a Wayland display server, a driver without extras):
		# pacman fails on no targets, so do nothing instead
		if not packages:
			return

		info(f'Installing packages: {packages}')

		flags = '--noconfirm --needed' + _QUIET_FLAGS
		conf = live(PACMAN_CONF)

		if self.target == Path('/'):
			cmd = f'pacman --config {conf} -S {" ".join(packages)} {flags}'
			bail = (
				'Package installation failed. See '
				f'{logger.host_path} or above message for error details'
			)
		else:
			# no -K: that inits an empty target keyring (RSA-4096 master key
			# gen, then archlinux-keyring's post_install lsigns every
			# trusted key from scratch). pacstrap already verified packages
			# with the host keyring, so let it copy that one in (its default
			# when -K/-G are absent).
			cmd = (
				f'pacstrap -C {conf} {self.target} '
				f'{" ".join(packages)} {flags}'
			)
			bail = (
				f'Pacstrap failed. See {logger.host_path} or above '
				'message for error details'
			)

		self.ask(
			'Could not strap in packages',
			bail,
			SysCommand,
			cmd,
			peek_output=True,
		)
