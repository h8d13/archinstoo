r"""ArchInstoo Linux Installer.

                               /$$
                              | $$
  /$$$$$$   /$$$$$$   /$$$$$$$| $$$$$$$
 |____  $$ /$$__  $$ /$$_____/| $$__  $$
  /$$$$$$$| $$  \__/| $$      | $$  \ $$
 /$$__  $$| $$      | $$      | $$  | $$
|  $$$$$$$| $$      |  $$$$$$$| $$  | $$
 \_______/|__/       \_______/|__/  |__/



 /$$                       /$$
|__/                      | $$
 /$$ /$$$$$$$   /$$$$$$$ /$$$$$$    /$$$$$$   /$$$$$$
| $$| $$__  $$ /$$_____/|_  $$_/   /$$__  $$ /$$__  $$
| $$| $$  \ $$|  $$$$$$   | $$    | $$  \ $$| $$  \ $$
| $$| $$  | $$ \____  $$  | $$ /$$| $$  | $$| $$  | $$
| $$| $$  | $$ /$$$$$$$/  |  $$$$/|  $$$$$$/|  $$$$$$/
|__/|__/  |__/|_______/    \___/   \______/  \______/

                   ░           ░
                              ░                                             ░     ░ ░░
                                                ░                   ░░         ░ ░░  ░
                                   ░▒▒▒░░    ▓▒▓▒▓▒░       ░      ░░  ░░  ░░░    ░   ░░
                         ░       ▓▒▓█▓▒▓██▓██▓▓▓▓░▒█  ░░ ░░ ░ ░░ ░░░ ░░ ░░  ░░░ ░  ░
                   ░░           ▓▒█▒█░█▒█████▓▓▒▒ ▒▒▓ ░░░   ░░ ░░░░░░░░░ ░ ░ ░░ ░░  ░░
                               ░▓▓▓░▒██████████████▓▒░░░░░░░░░░░░░░░░░ ░ ░░░ ░░░░ ░░░░░
            ░░                  ▒▓▒█████████████▓ █▓▒░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
           ██▒▓░▒░░▓ ▓▓▓ ▒▒▓▓██████▒██████▒▓░  ██ ░██▒▒▒▒▓▓░ ░░░░░░░░░░░░░░░░░░░░░░░░░░░
            ▒███▒             ░░ ░░▓█████▒███▒█▓ ▒█░░░▒▒▓██▒░░▒██▓▒▒░░░░░░░░░░░░░░░░░░░
               ▓██▓          ░░░░░░░░▒██▓██▓▒████▓█░░░░░░░░░░░░░▓█▓▒█░█▒░░░░░░░░░░░░░░░
                  ███       ░░░░░░░░░░░░▒▒█▓░█▓░▒ ░░░░░░░░░░░░░░░▓██▓░░░░░░░░░░░░░░░░░░
                    ░██▓     ░░░░░░░░░░░░▓▒█▒░ ░▓█░░░░░░░░░░░░░██▒░░░░░░░░░░░░░ ░░░░░░░
                       ▒██▓   ▒█▒░░░░░░▓▒██▒███▓▓██░░░░░░░░▒██▒░░░░░░░░░░░░░░ ▓ ░░░░░░░
                          ███▓██▒█▒░█▓██▓██▓██▒▓▒░░░███▒███▒░░░░░░░░░  ░░░░░░░░░ ░░░░░░
░                      ░░░░░█████▒█▓░▓▓█▒█▓█▒▓█████▓▒██▒█░░░░░▒   ░░░░▒░░░░░░░ ░░░░░░░░
                        ░░░░░████▒███▓▓▓▒▒░████▓░ ░▒▒██▒░▒░  ░░▒ ▒▒▒░░▒░▒▒▒▒▒░  ░▒░░░░░
░                       ░░░░░  ░▓█░▒██████▓██████▓▒░█░▒▒▒▒░ ▒▒▒▒  ░░░░▒░░░░░▒▒░░░░░░░
░░░░                      ░░░ ░▒███▒  ░  ░███████▓██▒░▒░░▒▒ ░░▒▒ ░▒▒▒▒░░░░░▒░▒░▒▒░░░░░░
░░░░░░                      ░░░░▓  ░▒██████▓████▒   ██░▒▒▒▒ ▒▒▒▒░▒▒▒▒▒▒░▒▒▒▒▒░▒░░░░░░ ░
░░░░░░░ ░                      ███▒ ░░   ░██████▒▓▓▒ █▒▒▒▒▒▒▒▒▒▒ ▒▒▒▒▒▒░▒▒▒▒▒ ░░░░░ ░
    ░  ░░░░░░░░                ▓░ ▒▓▓█▓▒░  ██████████▓▒▒▒▒▒▒▒▒▒▒░▒▒▒▒▒▒▒░▒▒▒░░░
      ░░░░░░░░░░               ▓██▓▒   ░▓███████▒   ░▒▒▒▒▒▒▒░▒▒▒░▒▒▒▒▒▒▒░░▒░░
        ░░░░░░░░░░░            ░▓        ░██████▒ ▓██▓▒▒▒▒▒▒ ▒▒▒ ▒▒▒▒▒▒▒  ░▒ ▒░░
          ░░░░░░░░░░░           ░██████▓░█▒▓▓░░░░█▓▓█▒▓▓▓▓▓▒░▒▒▒ ▒▒▒░ ░ ░░
            ░░░░░░░░░░░░         ▓▒    ▓▓ ▒▓▓░░░░░░▒▒▒▒▒▓▓▓▓▒░░▒   ░▒▒▒░

=> BL => FS => PM/BASE => KERN/H => DRIVERS => USERS/GROUPS => PROFILES
=> APPS(CAT) => MISC.
Base refers to a minimal install:
	=> Essential pkgs
	=> Locales, console, kb
	=> Pacman related
	=> Hostname, TZ/NTP

This roughly shows the `guided` flow.
Other scripts or skip flags allow to skip some or all of these steps and run
archinstoo the way you need it, you are also free to modify profiles or certain
install steps if desired.

Misc is up to preference, which is the entire goal of this project: enable & give
choices. But also lets standards compete in a better environment.
Banner made on 10/02/2026.
"""

import logging
import sys
import textwrap
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from . import deps
from ._version import GITSTAT, PKGVER, VERSION
from .lib import output
from .lib.checkpoints import _check_script, _run_script, clean_cache, clean_logs
from .lib.cli import build_parser
from .lib.exceptions import SysCallError
from .lib.hardware import SysInfo
from .lib.output import FormattedOutput, debug, error, info, log, logger, warn
from .lib.pm.pacman import Pacman
from .lib.tui.curses_menu import Tui
from .lib.utils.env import Env
from .lib.utils.host import Host, is_root, is_venv, kernel_info
from .lib.utils.net import ping

if TYPE_CHECKING:
	from .lib.args import ArchConfigHandler, Arguments

# scripts that do not need root access
ROOTLESS_SCRIPTS = frozenset({'list', 'mirror', 'count', 'schema', 'detect', 'dev.vm'})
# scripts that only touch the running system
NO_DISK_SCRIPTS = frozenset({'packages'})


def _log_env_info() -> None:
	# install.log is appended to, so consecutive runs land in one file and
	# read as duplicated output. Open each one with a line that says which
	# run it is
	info(f'Ver: {__name__} {PKGVER} ({GITSTAT})')

	# log which mode we are using
	info(f'Python path: {sys.executable} is_venv={is_venv()}')

	if Host.running_from_bootstrap():
		info('Running from the bootstrap root...')
	elif Host.running_from_host():
		info(f'Running from Host (H2T Mode) on {Host.running_from_who()}...')
	else:
		info('Running from ISO (USB Mode)...')

	info(f'Kernel: {kernel_info()}')
	info(f'Logger path: {logger.host_path}')


def _missing_deps(depends: tuple[str, ...]) -> list[str]:
	# -T prints only what is unsatisfied and honours `provides`, so a package
	# the ISO already covers under another name is left alone.
	try:
		Pacman.run(f'-T {" ".join(depends)}')
	except SysCallError as err:
		# -T exits 127 when it has names to report; anything else is the call
		# itself failing, and nothing can be concluded about the deps
		debug(f'pacman -T exited {err.exit_code}: {err}')
		if err.exit_code != 127:
			raise
		out = err.worker_log.decode('utf-8', errors='ignore')
		missing = [
			line.strip()
			for line in out.splitlines()
			if line.strip() in depends
		]
		if not missing:
			raise
		return missing

	return []


def _depends() -> tuple[str, ...]:
	# an Arch host/ISO already ships the disk tools
	if Host.running_from_bootstrap():
		return deps.BASE + deps.DISK
	return deps.BASE


def _fetch_deps() -> int:
	if Env.get_value('A2_DEPS_FETCHED'):
		info('Already fetched.')
		return 0
	try:
		debug('Fetching deps...')
		missing = _missing_deps(_depends())
		# mark in current env as bootstrapped
		if not missing:
			# nothing installed
			info('Deps already satisfied...')
			Env.put_value('A2_DEPS_FETCHED', '1')
			return 0

		info(f'Fetching {len(missing)} missing dep(s): {" ".join(missing)}')
		Pacman.run(
			f'-S --needed --noconfirm {" ".join(missing)}', peek_output=True
		)
		Env.put_value('A2_DEPS_FETCHED', '1')
	except Exception as e:
		error(f'Failed to fetch deps: {e}')
		return 1

	return 0


def _ensure_host_deps() -> int:
	# read-only: --script bootstrap installed these into its root, an H2T
	# Arch installs them with its own pacman; a miss stops here, not mid-install
	if missing := _missing_deps(_depends()):
		error(f'Missing host deps: {" ".join(missing)}')
		info(f'Install them first: pacman -Syu --needed {" ".join(missing)}')
		return 1
	return 0


def _check_online() -> int:
	try:
		ping('1.1.1.1')
		debug('Network reachable')
		return 0
	except OSError as ex:
		if 'Network is unreachable' in str(ex):
			error('No network connectivity (ping 1.1.1.1 failed)')
			info('Use iwctl/nmcli to connect manually.')
			return 1
		raise


def _prepare(offline: bool) -> int:
	# log python/host-2-target
	_log_env_info()

	if not is_root():
		return 0

	# pacman, its config and keyring only exist on Arch: any other host runs
	# archinstoo inside the bootstrap script's Arch root instead
	if Host.running_from_foreign():
		error(
			f'Running on {Host.running_from_who() or "an unknown host"}: '
			'start through --script bootstrap, which runs from any Linux '
			'host.'
		)
		return 1

	if not offline and (rc := _check_online()):
		return rc

	if Host.running_from_bootstrap() or Host.running_from_arch_host():
		return _ensure_host_deps()

	# the ISO from here: fully offline installs should be possible
	if offline:
		return 0

	# -Syy then -S without -u is a partial upgrade: fine on a live system
	try:
		info('Fetching db...')
		Pacman.run('-Syy', peek_output=True)
		return _fetch_deps()
	except Exception as e:
		error('Failed to prepare app.')
		if 'could not resolve host' in str(e).lower():
			error(
				'Most likely due to a missing network connection or '
				'DNS issue. Or dependency resolution.'
			)

		error(
			'Run archinstoo --debug and check '
			f'{logger.host_path} for details.'
		)

		debug(f'Failed to prepare app: {e}')
		return 1


def _log_sys_info(args: Arguments) -> None:
	bitness = SysInfo.bitness()
	debug(
		f'Hardware model detected: {SysInfo.sys_vendor()} '
		f'{SysInfo.product_name()}'
	)
	debug(
		f'UEFI mode: {SysInfo.has_uefi()} Bitness: '
		f'{bitness if bitness is not None else "N/A"} Arch: {SysInfo.arch()}'
	)
	debug(f'Processor model detected: {SysInfo.cpu_model()}')
	debug(f'Memory statistics: {SysInfo.mem_total()} kB total installed')
	debug(f'Virtualization detected is VM: {SysInfo.is_vm()}')

	if args.debug:
		from .lib.disk.utils import disk_layouts

		debug(f'Disk states before installing:\n{disk_layouts()}')


def main(script: str, handler: ArchConfigHandler) -> int:
	# Usually ran straight as a module: python -m archinstoo or compiled as a
	# package. In any case we will be attempting to load the provided script to be
	# run from the scripts/ folder
	args = handler.args

	if not is_root():
		print(
			f'archinstoo {script} requires root privileges to '
			'run. See --help for more.'
		)
		return 1

	# fixes #4149 by passing args properly to subscripts
	handler.pass_args_to_subscript()
	_log_sys_info(args)

	# On host, snapshot /etc/pacman.conf and restore it on exit so an H2T run
	# never leaves the running system with a modified pacman.conf (heals a
	# prior crashed run too).
	from .lib.pm.config import guard_host_conf

	guard_host_conf()

	# usually 'guided' from default lib/args
	_run_script(script)

	return 0


def _error_message(exc: Exception, handler: ArchConfigHandler) -> None:
	err = ''.join(traceback.format_exception(exc))
	error(err)

	text = textwrap.dedent(f"""\
		Archinstoo experienced the above error. If you think this is a bug,
		please report it to {handler.config.bug_report_url}
		and include the log file "{logger.host_path}".

		Hint: To extract the log from a live ISO
		curl --data-binary @{logger.host_path} https://paste.rs
	""")

	warn(text)


def _is_bootstrap_blocked(script: str | None) -> bool:
	# these install onto the running system (target '/'), which under
	# --script bootstrap is the throwaway root: the work would vanish with it
	return script in NO_DISK_SCRIPTS and Host.running_from_bootstrap()


def _run_bootstrap() -> int:
	if Host.running_from_bootstrap():
		error(
			'archinstoo --script bootstrap: already inside the '
			'bootstrap root'
		)
		return 1
	argv = sys.argv[1:]
	split = argv.index('--') if '--' in argv else len(argv)
	head = argv[:split]
	own = [a for a in head if a in {'-h', '--help'}]
	# options before -- would be parsed here and never reach the root
	if extra := [
		a
		for a in head
		if a
		not in {'--script', 'bootstrap', '--script=bootstrap', '--debug', *own}
	]:
		error(
			'archinstoo --script bootstrap: pass '
			f'{" ".join(extra)} after --, it runs inside the root'
		)
		return 1
	sys.argv = [sys.argv[0], *own, '--', *argv[split + 1 :]]
	_run_script('bootstrap')
	return 0


def run_as_a_module() -> int:
	# the real grammar before any preparation (-v/--version exits here). No
	# default for --script: the bare global help needs "not given" visible
	parser = build_parser()
	parser.set_defaults(script=None)
	early, remaining = parser.parse_known_args()
	# add_help=False: -h stays unparsed, for the global help or the script's
	is_help = '-h' in remaining or '--help' in remaining

	# short-circuit for global help (no --script) before any preparation
	if is_help and early.script is None:
		build_parser().print_help()
		return 0

	# set debug early before heavy imports
	if early.debug:
		output.log_level = logging.DEBUG

	# a missing or malformed name (nope, dev/vm) fails here, not after root
	# checks and bootstrap
	if early.script is not None:
		_check_script(early.script)

	# runs on the host's python before any dep exists: everything else
	# happens inside its root, with the args given after --
	if early.script == 'bootstrap':
		return _run_bootstrap()

	if _is_bootstrap_blocked(early.script):
		error(
			f'archinstoo {early.script} configures the running '
			'system, which is the bootstrap root.'
		)
		error('Run it on the installed system instead.')
		return 1

	is_rootless = early.script in ROOTLESS_SCRIPTS
	# skip bootstrap for rootless scripts or help requests
	if not is_rootless and not is_help and (rc := _prepare(early.offline)):
		return rc

	# now safe to import after bootstrap (or skipped for rootless)
	from .lib.args import get_arch_config_handler

	handler = get_arch_config_handler()
	script = handler.get_script()
	source = handler.args.config or handler.args.config_url or 'menu'
	run = f'Script: {script} silent={handler.args.silent} config={source}'

	# handle rootless scripts early
	if is_rootless:
		# their stdout is the report: the run header stays a debug line
		debug(run)
		if is_root():
			warn(f'archinstoo {script} does not need root privileges.')

		handler.pass_args_to_subscript()
		_run_script(script)
		return 0

	info(run)

	# now handle root scripts
	try:
		rc = 0
		exc = None

		try:
			rc = main(script, handler)
		except KeyboardInterrupt:
			# clean user abort: no traceback / bug-report noise. 128+SIGINT,
			# what an uncaught ^C exits with, so callers can
			# tell it from a failure
			warn('Aborted by user.')
			rc = 130
		except Exception as e:
			exc = e
		finally:
			# restore the terminal to the original state
			Tui.shutdown()

		if exc:
			_error_message(exc, handler)
			rc = 1

		return rc

	finally:
		if handler.args.clean:
			# note this deletes all logs too
			info(f'--clean: removing {logger.directory}')
			clean_logs()
		# removes any __pycache__ if possible
		clean_cache(Path(__file__).parent.parent)


__all__ = [
	'VERSION',
	'FormattedOutput',
	'Pacman',
	'SysInfo',
	'Tui',
	'debug',
	'error',
	'info',
	'log',
	'warn',
]
