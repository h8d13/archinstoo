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

=> BL => FS => PM/BASE => KERN/H => DRIVERS => USERS/GROUPS => PROFILES => APPS(CAT) => MISC.
Base refers to a minimal install:
	=> Essential pkgs
	=> Locales, console, kb
	=> Pacman related
	=> Hostname, TZ/NTP

This roughly shows the `guided` flow.
Other scripts or skip flags allow to skip some or all of these steps and run archinstoo.
The way you need it, you are also free to modify profiles or certain install steps if desired.

Misc is up to preference, which is the entire goal of this project: enable & give choices.
But also lets standards compete in a better environment. Banner made on 10/02/2026.
"""

import logging
import sys
import textwrap
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from ._version import __gitstat__, __pkgver__, __version__
from .lib import output
from .lib.checkpoints import _check_script, _run_script, clean_cache, clean_logs
from .lib.cli import build_parser
from .lib.exceptions import SysCallError
from .lib.hardware import SysInfo
from .lib.output import FormattedOutput, debug, error, info, log, logger, warn
from .lib.pm.bootstrap import keyring_init, pacman_conf
from .lib.pm.pacman import Pacman
from .lib.tui.curses_menu import Tui
from .lib.utils.env import Env
from .lib.utils.host import Host, is_root, is_venv, kernel_info
from .lib.utils.net import ping

if TYPE_CHECKING:
	from .lib.args import ArchConfigHandler, Arguments

# comment columns are read as a table, ruff would collapse them
# fmt: off
base_depends = (
	'systemd',  	        # For systemd-based operations
	'coreutils',  	        # Basic utilities
	'util-linux',  	        # For partition utilities
	'pciutils',  	        # For PCI device detection
	'kbd',  	        # For keyboard layout configuration
	'pacman',
	'git',  	        # Cloning stashes
	'arch-install-scripts', # For pacstrap, genfstab, chroot
	'python-pyparted',
	'dosfstools',  	        # FAT EFI filesystem support
)
disk_depends = (
	'btrfs-progs', 		# btrfs filesystem support
	'e2fsprogs',  		# ext4 filesystem support
	'f2fs-tools',  		# f2fs filesystem support
	'xfsprogs',  		# XFS filesystem support
	'cryptsetup',  		# LUKS encryption support
	'lvm2',  		# LVM layout support
	'mdadm',		# RAID layout support
)
# we only check these on bootstrap tarball.
# https://gitlab.archlinux.org/archlinux/archiso/-/blob/master/configs/releng/packages.x86_64
# mirror the PKGBUILDs in repo
# fmt: on

# main init file of archinstoo
# we will log some useful info
# checks launch pre-conditions
# and bootstrap the lib's deps
# handle default guided script
# rootless/needsroot utilities

# 2 different bootstrap paths.
# arch host/ISO vs ext distros
# fetch deps directly on arch.
# assume host sided pkg others

# scripts that don't need root
# short-circuit all of the ini

# scripts that do not need root access
ROOTLESS_SCRIPTS = frozenset({'list', 'mirror', 'count', 'schema', 'detect', 'dev.vm'})
# scripts that only touch the running system
NO_DISK_SCRIPTS = frozenset({'packages'})


def _log_env_info() -> None:
	# install.log is appended to, so consecutive runs land in one file and
	# read as duplicated output. Open each one with a line that says which
	# run it is
	info(f'Ver: {__name__} {__pkgver__} ({__gitstat__})')

	# log which mode we are using
	info(f'Python path: {sys.executable} is_venv={is_venv()}')

	if Host.running_from_host():
		info(f'Running from Host (H2T Mode) on {Host.running_from_who()}...')
	else:
		info('Running from ISO (USB Mode)...')

	info(f'Kernel: {kernel_info()}')
	info(f'Logger path: {logger.path}')


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
		missing = [line.strip() for line in out.splitlines() if line.strip() in depends]
		if not missing:
			raise
		return missing

	return []


def _depends() -> tuple[str, ...]:
	# an Arch host/ISO already ships the disk tools
	if Host.running_from_bootstrap():
		return base_depends + disk_depends
	return base_depends


def _bootstrap() -> int:
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
		Pacman.run(f'-S --needed --noconfirm {" ".join(missing)}', peek_output=True)
		Env.put_value('A2_DEPS_FETCHED', '1')
	except Exception as e:
		error(f'Failed to fetch deps: {e}')
		return 1

	return 0


def _ensure_host_deps() -> int:
	# read-only: an H2T host installs these with its own pacman, so a miss
	# stops here instead of as a traceback mid-install
	if missing := _missing_deps(base_depends):
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

	# check online (or offline requested) before trying to fetch packages
	if not offline:
		if rc := _check_online():
			return rc
		# note indent fully offlines installs should be possible
		try:
			# -Syy then -S without -u is a partial upgrade of the running system:
			# fine on the ISO, not on the user's own Arch, which provides the deps
			if Host.running_from_arch_host():
				return _ensure_host_deps()
			# a foreign host ships pacman but none of its config/keyring; build
			# it first (conf before keyring: pacman-key reads pacman.conf).
			foreign_host = Host.running_from_foreign()
			if foreign_host:
				pacman_conf()
				keyring_init()
			info('Fetching db...')
			Pacman.run('-Syy', peek_output=True)
			# python deps come from the host package manager on a foreign host
			# we only bootstrap pacman related files: ex Alpine ISOs
			if not foreign_host and (rc := _bootstrap()):
				return rc
			# however if in a bootstrap tarball we need to install disk depends.
		except Exception as e:
			error('Failed to prepare app.')
			if 'could not resolve host' in str(e).lower():
				error('Most likely due to a missing network connection or DNS issue. Or dependency resolution.')

			error(f'Run archinstoo --debug and check {logger.path} for details.')

			debug(f'Failed to prepare app: {e}')
			return 1

	return 0


def _log_sys_info(args: Arguments) -> None:
	bitness = SysInfo.bitness()
	debug(f'Hardware model detected: {SysInfo.sys_vendor()} {SysInfo.product_name()}')
	debug(f'UEFI mode: {SysInfo.has_uefi()} Bitness: {bitness if bitness is not None else "N/A"} Arch: {SysInfo.arch()}')
	debug(f'Processor model detected: {SysInfo.cpu_model()}')
	debug(f'Memory statistics: {SysInfo.mem_total()} kB total installed')
	debug(f'Virtualization detected is VM: {SysInfo.is_vm()}')

	if args.debug:
		from .lib.disk.utils import disk_layouts

		debug(f'Disk states before installing:\n{disk_layouts()}')


def main(script: str, handler: ArchConfigHandler) -> int:
	# Usually ran straight as a module: python -m archinstoo or compiled as a package.
	# In any case we will be attempting to load the provided script to be run from the scripts/ folder
	args = handler.args

	if not is_root():
		print(f'archinstoo {script} requires root privileges to run. See --help for more.')
		return 1

	# fixes #4149 by passing args properly to subscripts
	handler.pass_args_to_subscript()
	_log_sys_info(args)

	# On host, snapshot /etc/pacman.conf and restore it on exit so an H2T run never leaves
	# the running system with a modified pacman.conf (heals a prior crashed run too).
	from .lib.pm.config import guard_host_conf

	guard_host_conf()

	# usually 'guided' from default lib/args
	_run_script(script)

	return 0


def _error_message(exc: Exception, handler: ArchConfigHandler) -> None:
	err = ''.join(traceback.format_exception(exc))
	error(err)

	text = textwrap.dedent(f"""\
		Archinstoo experienced the above error. If you think this is a bug, please report it to
		{handler.config.bug_report_url} and include the log file "{logger.path}".

		Hint: To extract the log from a live ISO
		curl --data-binary @{logger.path} https://paste.rs
	""")

	warn(text)


def _is_foreign_blocked(script: str | None) -> bool:
	# a foreign host gets its deps from its own package manager (see distros/)
	# and pacstraps a separate target, which is fine. these scripts instead
	# install onto the running system: target '/' means `pacman -S` straight
	# into the Debian/Alpine root, never a chroot. distros/BOOT's Arch root
	# is thrown away after, same outcome.
	return script in NO_DISK_SCRIPTS and (Host.running_from_foreign() or Host.running_from_bootstrap())


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

	if _is_foreign_blocked(early.script):
		running = 'the distros/BOOT bootstrap root' if Host.running_from_bootstrap() else Host.running_from_who() or 'not Arch'
		error(f'archinstoo {early.script} configures the running system, which is {running}.')
		error('Use a disk script from a foreign host (see distros/), or run this one from an Arch host/ISO.')
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
			# what an uncaught ^C exits with, so callers can tell it from a failure
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
	'FormattedOutput',
	'Pacman',
	'SysInfo',
	'Tui',
	'__version__',
	'debug',
	'error',
	'info',
	'log',
	'warn',
]
