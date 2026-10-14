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
	=> dnf related
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
from .lib.checkpoints import _run_script, clean_cache, clean_logs
from .lib.cli import build_parser
from .lib.exceptions import SysCallError
from .lib.general import SysCommand
from .lib.hardware import SysInfo
from .lib.output import FormattedOutput, debug, error, info, log, logger, warn
from .lib.tui.curses_menu import Tui
from .lib.utils.env import Os, is_root, is_venv, kernel_info
from .lib.utils.net import ping

if TYPE_CHECKING:
	from .lib.args import ArchConfigHandler, Arguments

# what the installer runs on the host side, Fedora package names. BOOT
# installs the same set into its root; a Fedora host brings them itself
# comment columns are read as a table, ruff would collapse them
# fmt: off
host_depends = (
	'systemd',              # systemctl, bootctl, kernel-install
	'systemd-udev',         # udevadm
	'coreutils',            # Basic utilities
	'util-linux',           # lsblk, findmnt, mount
	'pciutils',             # For PCI device detection
	'kbd',                  # For keyboard layout configuration
	'libxcrypt',            # crypt.py dlopen
	'dnf5',                 # strapping the target
	'git',                  # Cloning stashes
)
# only what partitions and formats: the running-system scripts skip these
disk_depends = (
	'python3-pyparted',     # partitioning
	'dosfstools',           # FAT EFI filesystem support
	'btrfs-progs',          # btrfs filesystem support
	'e2fsprogs',            # ext4 filesystem support
	'f2fs-tools',           # f2fs filesystem support
	'xfsprogs',             # XFS filesystem support
	'cryptsetup',           # LUKS encryption support
	'cracklib-dicts',       # pwquality's dictionary, cryptsetup checks passphrases
	'lvm2',                 # LVM layout support
	'mdadm',                # RAID layout support
)
# fmt: on

# scripts that do not need root access
ROOTLESS_SCRIPTS = frozenset({'list'})
# scripts that only touch the running system
NO_DISK_SCRIPTS = frozenset({'packages'})


def _log_env_info() -> None:
	# install.log is appended to, so consecutive runs land in one file and
	# read as duplicated output. Open each one with a line that says which
	# run it is
	info(f'Ver: {__name__} {__pkgver__} ({__gitstat__})')

	# log which mode we are using
	info(f'Python path: {sys.executable} is_venv={is_venv()}')

	if Os.running_from_bootstrap():
		info('Running from the BOOT root...')
	else:
		info(f'Running from Host (H2T Mode) on {Os.os_release("ID") or "unknown"}...')

	info(f'Kernel: {kernel_info()}')
	info(f'Logger path: {logger.path}')


def _missing_deps(depends: tuple[str, ...]) -> list[str]:
	# rpm -q names every package it lacks as "package X is not installed"
	# and exits with that count
	try:
		SysCommand(['rpm', '-q', '--whatprovides', *depends])
	except SysCallError as err:
		out = err.worker_log.decode('utf-8', errors='ignore')
		missing = [name for name in depends if f'no package provides {name}' in out or f'package {name} is not installed' in out]
		if not missing:
			raise
		return missing
	return []


def _check_online() -> int:
	try:
		ping('1.1.1.1')
		debug('Network reachable')
		return 0
	except OSError as ex:
		if 'Network is unreachable' in str(ex):
			error('No network connectivity (ping 1.1.1.1 failed)')
			info('Connect the host first (nmcli, iwctl, ...).')
			return 1
		raise


def _prepare(offline: bool, disk: bool) -> int:
	# log python/host-2-target
	_log_env_info()

	if not is_root():
		return 0

	# BOOT's throwaway root, or the user's own Fedora: anything else has no
	# dnf or rpm database to strap from
	if not (Os.running_from_bootstrap() or Os.running_from_fedora_host()):
		error(f'Running on {Os.os_release("ID") or "an unknown host"}: start through ./BOOT, which runs from any Linux host.')
		return 1

	if not offline and (rc := _check_online()):
		return rc

	# read-only either way: BOOT installed these, a Fedora host installs them
	# with its own dnf, so a miss stops here instead of mid-install
	if missing := _missing_deps(host_depends + disk_depends if disk else host_depends):
		error(f'Missing host deps: {" ".join(missing)}')
		info(f'Install them first: dnf install {" ".join(missing)}')
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


def _is_bootstrap_blocked(script: str | None) -> bool:
	# these install onto the running system (target '/'), which under BOOT
	# is the throwaway root: the work would vanish with it
	return script in NO_DISK_SCRIPTS and Os.running_from_bootstrap()


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

	if _is_bootstrap_blocked(early.script):
		error(f'archinstoo {early.script} configures the running system, which is the BOOT bootstrap root.')
		error('Run it on the installed Fedora instead.')
		return 1

	is_rootless = early.script in ROOTLESS_SCRIPTS
	# skip bootstrap for rootless scripts or help requests
	if not is_rootless and not is_help and (rc := _prepare(early.offline, early.script not in NO_DISK_SCRIPTS)):
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
	'SysInfo',
	'Tui',
	'__version__',
	'debug',
	'error',
	'info',
	'log',
	'warn',
]
