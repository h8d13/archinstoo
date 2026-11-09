import contextlib
import re
import shlex
import shutil
import sys
import tempfile
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Final

from archinstoo.lib.exceptions import RequirementError, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.linux_path import LPath
from archinstoo.lib.output import debug, error, info, logger, warn
from archinstoo.lib.pm.errors import (
	Failure,
	FailureKind,
	classify,
	strip_version,
)
from archinstoo.lib.pm.recovery import (
	RETRY,
	Recovery,
	ask_text,
	package,
	prompt,
)
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
_SILENT = '--silent' in sys.argv
_QUIET_FLAGS = ' --noprogressbar' if _SILENT else ''


class Pacman:
	def __init__(self, target: Path) -> None:
		self.target = target
		# skipped while recovering, re-listed when the install ends
		self.dropped_packages: list[str] = []

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

	def strap(self, packages: str | list[str]) -> None:
		# no -Sy here: pacstrap syncs the target's own db, and '/' installs
		# against the db _prepare synced (ISO) or the user keeps (Arch host)
		if isinstance(packages, str):
			packages = [packages]

		# nothing asked (a Wayland display server, a driver without extras):
		# pacman fails on no targets, so do nothing instead
		if not packages:
			return

		packages = list(packages)
		extra: list[str] = []
		seen: set[str] = set()

		while packages:
			info(f'Installing packages: {packages}')
			try:
				SysCommand(
					self._strap_cmd(packages, extra),
					peek_output=True,
				)
				return
			except SysCallError as err:
				error(f'Could not strap in packages: {err}')
				if not self._recover(err, packages, extra, seen):
					raise RequirementError(
						self._bail_message()
					) from err

		# everything asked for got skipped on the way; report_dropped lists
		# it again once the install ends
		warn('Continuing without the remaining packages')

	def _strap_cmd(self, packages: list[str], extra: list[str]) -> str:
		# extra: flags recovery added, --overwrite or --ask, already quoted
		flags = '--noconfirm --needed' + _QUIET_FLAGS
		flags += ''.join(f' {flag}' for flag in extra)
		conf = live(PACMAN_CONF)
		names = ' '.join(packages)

		if self.target == Path('/'):
			return f'pacman --config {conf} -S {names} {flags}'
		# no -K: that inits an empty target keyring (RSA-4096 master key
		# gen, then archlinux-keyring's post_install lsigns every
		# trusted key from scratch). pacstrap already verified packages
		# with the host keyring, so let it copy that one in (its default
		# when -K/-G are absent).
		return f'pacstrap -C {conf} {self.target} {names} {flags}'

	def _bail_message(self) -> str:
		what = (
			'Package installation'
			if self.target == Path('/')
			else 'Pacstrap'
		)
		return (
			f'{what} failed. See {logger.host_path} or above '
			'message for error details'
		)

	def _hint(self) -> str:
		if self.target == Path('/'):
			return 'Installing onto the running system: fix it with pacman.'
		return (
			f'The target is mounted at {self.target}: '
			f'"arch-chroot {self.target}" works inside it.'
		)

	def _recover(
		self,
		err: SysCallError,
		packages: list[str],
		extra: list[str],
		seen: set[str],
	) -> bool:
		# packages and extra flags change in place. True when something
		# changed and a retry makes sense, False to raise the original error
		output = _error_output(err)
		failure = classify(output)

		# keyring and pacman.conf resets fix whole classes of failures with
		# no question asked: each gets one try before the prompt
		if fix := _auto_fix(failure, output.lower()):
			name = f'auto:{fix.__name__}'
			if name not in seen:
				seen.add(name)
				if fix():
					return True

		# the same failure twice in a row: what was offered last time did
		# not help, so stop offering it
		signature = f'{failure.kind}:{",".join(failure.candidates)}'
		repeated = signature in seen
		seen.add(signature)

		droppable = [n for n in failure.candidates if _requested(packages, n)]
		options = _recovery_options(failure, droppable, repeated)

		detail = failure.summary
		if not options and failure.candidates and not droppable:
			detail += (
				f'\n{", ".join(failure.candidates)} was pulled in as a '
				'dependency, so it cannot be dropped from the request.'
			)

		choice = prompt(
			_HEADERS[failure.kind],
			options,
			detail=detail,
			hint=self._hint(),
			interactive=not _SILENT,
		)

		if choice == RETRY:
			return True
		if choice == 'overwrite':
			extra.extend(
				f'--overwrite {shlex.quote(p)}' for p in failure.paths
			)
			return True

		before = list(packages)
		# each branch is only offered when droppable holds what it names
		match choice:
			case 'keep_first':
				self._drop(packages, droppable[1])
				_replace_conflicting(extra)
			case 'keep_second':
				self._drop(packages, droppable[0])
				_replace_conflicting(extra)
			case 'drop':
				self._drop(packages, *droppable)
			case 'rename':
				self._rename(packages, droppable[0])
			case 'abandon':
				self._drop(packages, *packages)
			case _:
				# not a key this loop offered: nothing to change
				pass

		if packages == before:
			warn('Nothing changed, so a retry would fail the same way')
			return False
		return True

	def _drop(self, packages: list[str], *names: str) -> None:
		targets = {strip_version(name) for name in names}
		kept = []
		for entry in packages:
			if strip_version(entry) in targets:
				warn(f'Skipping {entry}')
				self.dropped_packages.append(entry)
			else:
				kept.append(entry)
		packages[:] = kept

	def _rename(self, packages: list[str], name: str) -> None:
		replacement = ask_text(f'Package name to use instead of {name}: ')
		if not replacement:
			warn(f'No replacement given, keeping {name}')
			return

		target = strip_version(name)
		packages[:] = [
			replacement if strip_version(entry) == target else entry
			for entry in packages
		]
		info(f'Replaced {name} with {replacement}')


_HEADERS: Final = {
	FailureKind.CONFLICT: 'Package conflict',
	FailureKind.FILE_EXISTS: 'Conflicting files on the target',
	FailureKind.MISSING_TARGET: 'Package not found',
	FailureKind.UNSATISFIED_DEPENDENCY: 'Unsatisfiable dependency',
	FailureKind.UNKNOWN: 'Package installation failed',
}


def _auto_fix(failure: Failure, output: str) -> Callable[[], bool] | None:
	# the resets archinstoo always applied, now ahead of the prompt
	if failure.kind not in {
		FailureKind.UNKNOWN,
		FailureKind.UNSATISFIED_DEPENDENCY,
	}:
		return None
	if 'invalid or corrupted package' in output:
		warn('Detected corrupted package: resetting keyring and retrying...')
		return Pacman.reset_keyring
	if any(s in output for s in ('gpgme error', 'no data', 'signature')):
		warn('Detected keyring/signature issue: resetting keyring...')
		return Pacman.reset_keyring
	if 'could not satisfy dependencies' in output:
		warn('Detected dependency issue: resetting pacman.conf...')
		return reset_conf
	return None


_SKIP_REST: Final = 'Skip the remaining packages and continue the installation'
_SKIP_THESE: Final = 'Skip these packages and continue the installation'


def _recovery_options(
	failure: Failure, droppable: list[str], repeated: bool
) -> list[Recovery]:
	if repeated:
		return [Recovery('abandon', _SKIP_REST)]

	first, *rest = failure.candidates or ('',)
	second = rest[0] if rest else ''
	drop = None
	if droppable:
		drop = Recovery('drop', f'Drop {package(droppable[0])} and continue')

	match failure.kind:
		case FailureKind.CONFLICT if len(droppable) == 2:
			a, b = package(first), package(second)
			return [
				Recovery('keep_first', f'Keep {a} and drop {b}'),
				Recovery('keep_second', f'Keep {b} and drop {a}'),
				Recovery(
					'drop', f'Keep neither {a} nor {b} and continue'
				),
			]
		case FailureKind.MISSING_TARGET if drop:
			rename = f'Replace {package(first)} with another package name'
			return [Recovery('rename', rename), drop]
		case FailureKind.CONFLICT | FailureKind.UNSATISFIED_DEPENDENCY if drop:
			return [drop]
		case FailureKind.FILE_EXISTS:
			overwrite = Recovery(
				'overwrite', 'Overwrite the conflicting files and retry'
			)
			return [overwrite, drop] if drop else [overwrite]
		case FailureKind.UNKNOWN:
			return [
				Recovery(RETRY, 'Retry installing these packages'),
				Recovery('abandon', _SKIP_THESE),
			]
		case _:
			return []


# answers pacman's "Remove <package>? [y/N]" conflict question with yes
# (ALPM_QUESTION_CONFLICT_PKG)
_REPLACE_CONFLICTING: Final = '--ask=4'


def _replace_conflicting(extra: list[str]) -> None:
	# the side the user dropped may already be on the target from an earlier
	# step: then --noconfirm answers pacman's removal question with no and
	# the retry fails the same way. Only after an explicit keep choice
	if _REPLACE_CONFLICTING not in extra:
		extra.append(_REPLACE_CONFLICTING)


def _requested(packages: list[str], name: str) -> bool:
	# asked for directly, as opposed to pulled in as a dependency
	target = strip_version(name)
	return any(strip_version(entry) == target for entry in packages)


def _error_output(err: SysCallError) -> str:
	# str(err) keeps only the last 500 characters, which routinely cuts
	# the line naming the conflict; worker_log is the whole, cleaned run
	if err.worker_log:
		return err.worker_log.decode('utf-8', errors='replace')
	return str(err)
