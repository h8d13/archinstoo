"""Arch Linux installer - guided, templates etc."""

import logging
import sys
import textwrap
import traceback
from typing import TYPE_CHECKING

from .lib import Pacman, output
from .lib.hardware import SysInfo
from .lib.output import FormattedOutput, debug, error, info, log, logger, warn
from .lib.translationhandler import Language, tr, translation_handler
from .lib.tui.curses_menu import Tui
from .lib.utils.env import Os, _run_script, clean_cache, is_root, is_venv, reload_python
from .lib.utils.net import ping

if TYPE_CHECKING:
	from .lib.args import ArchConfigHandler, Arguments

hard_depends = ('python-pyparted',)

# main init file of archinstoo
# we will log some useful info
# checks launch pre-conditions
# and bootstrap the lib's deps
# handle default guided script
# rootless/needsroot utilities

# scripts that don't need root
ROOTLESS_SCRIPTS = {'list', 'size', 'mirror'}


def _log_env_info() -> None:
	# log which mode we are using
	info(f'{sys.executable} is_venv={is_venv()}')

	if Os.running_from_host():
		info(f'Running from Host (H2T Mode) on {Os.running_from_who()}...')
	else:
		info('Running from ISO (USB Mode)...')


def _bootstrap() -> int:
	if Os.get_env('ARCHINSTALL_DEPS_FETCHED'):
		info('Already bootstrapped...')
		return 0
	try:
		info('Fetching deps...')
		Pacman.run(f'-S --needed --noconfirm {" ".join(hard_depends)}', peek_output=True)
		# mark in current env as bootstraped
		# avoid infinite reloads
		# refresh python last then re-exec to load new libraries
		Pacman.run('-S --needed --noconfirm python', peek_output=True)
		Os.set_env('ARCHINSTALL_DEPS_FETCHED', '1')
	except Exception:
		info('Failed to fetch deps.')
		return 1
	info('Reloading python...')
	try:
		reload_python()
	except Exception:
		info('Failed to reload python.')
		return 1

	return 0


def _check_online() -> int:
	try:
		ping('1.1.1.1')
		return 0
	except OSError as ex:
		if 'Network is unreachable' in str(ex):
			info('Use iwctl/nmcli to connect manually.')
			return 1
		raise


def _prepare() -> int:
	# log python/host-2-target
	_log_env_info()

	if is_venv() or not is_root():
		return 0

	# check online (or offline requested) before trying to fetch packages
	if '--offline' not in sys.argv:
		if rc := _check_online():
			return rc
		# note indent fully offlines installs should be possible
		# instead of importing full handler use sys.argv directly
		try:
			info('Fetching db...')
			Pacman.run('-Sy', peek_output=True)
			if rc := _bootstrap():
				return rc
		except Exception as e:
			error('Failed to prepare app.')
			if 'could not resolve host' in str(e).lower():
				error('Most likely due to a missing network connection or DNS issue. Or dependency resolution.')

			error(f'Run archinstall --debug and check {logger.path} for details.')

			debug(f'Failed to prepare app: {e}')
			return 1

	return 0


def _log_sys_info(args: Arguments) -> None:
	info(f'Hardware model detected: {SysInfo.sys_vendor()} {SysInfo.product_name()}')
	bitness = SysInfo._bitness()
	info(f'UEFI mode: {SysInfo.has_uefi()} Bitness: {bitness if bitness is not None else "N/A"} Arch: {SysInfo.arch()}')
	info(f'Processor model detected: {SysInfo.cpu_model()}')
	info(f'Memory statistics: {SysInfo.mem_total()} total installed')
	info(f'Graphics devices detected: {SysInfo._graphics_devices().keys()}')
	if args.debug:
		from .lib.disk.utils import disk_layouts

		debug(f'Virtualization detected is VM: {SysInfo.is_vm()}')
		debug(f'Disk states before installing:\n{disk_layouts()}')


def main(script: str, handler: ArchConfigHandler) -> int:
	"""
	Usually ran straight as a module: python -m archinstall or compiled as a package.
	In any case we will be attempting to load the provided script to be run from the scripts/ folder
	"""
	args = handler.args

	if not is_root():
		print(tr('archinstall {script} requires root privileges to run. See --help for more.').format(script=script))
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
		Archinstall experienced the above error. If you think this is a bug, please report it to
		{handler.config.bug_report_url} and include the log file "{logger.path}".

		Hint: To extract the log from a live ISO
		curl -F 'file=@{logger.path}' https://0x0.st
	""")

	warn(text)


def _script_from_argv() -> str | None:
	# peek at sys.argv for --script value without full arg parsing
	try:
		idx = sys.argv.index('--script')
		return sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
	except ValueError:
		return None


def run_as_a_module() -> int:
	# short-circuit for global help (no --script) before any preparation
	if ('-h' in sys.argv or '--help' in sys.argv) and '--script' not in sys.argv:
		from .lib.args import get_arch_config_handler

		get_arch_config_handler().print_help()
		return 0

	# set debug early from sys.argv before heavy imports
	if '--debug' in sys.argv:
		output.log_level = logging.DEBUG

	script_peek = _script_from_argv()

	is_rootless = script_peek in ROOTLESS_SCRIPTS
	# only bootstrap for scripts that need root
	if not is_rootless and (rc := _prepare()):
		return rc

	# now safe to import after bootstrap (or skipped for rootless)
	from .lib.args import get_arch_config_handler

	handler = get_arch_config_handler()
	script = handler.get_script()

	# handle rootless scripts early
	if is_rootless:
		if is_root():
			warn(f'archinstall {script} does not need root privileges.')

		handler.pass_args_to_subscript()
		_run_script(script)
		return 0

	if handler.args.debug:
		output.log_level = logging.DEBUG

	# now handle root scripts
	try:
		rc = 0
		exc = None

		try:
			rc = main(script, handler)
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
			handler.clean_up()
		clean_cache('.')


__all__ = [
	'FormattedOutput',
	'Language',
	'Pacman',
	'SysInfo',
	'Tui',
	'debug',
	'error',
	'info',
	'log',
	'translation_handler',
	'warn',
]
