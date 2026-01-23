"""Arch Linux installer - guided, templates etc."""

import importlib
import logging
import sys
import textwrap
import traceback

from .lib import Pacman, output
from .lib.hardware import SysInfo
from .lib.output import FormattedOutput, debug, error, info, log, logger, warn
from .lib.translationhandler import Language, tr, translation_handler
from .lib.tui.curses_menu import Tui
from .lib.utils.env import Os, is_root, is_venv, reload_python, running_from_host
from .lib.utils.net import ping


def _log_env_info() -> None:
	# log which mode we are using
	info(f'{sys.executable} is_venv={is_venv()}')

	if running_from_host():
		info('Running from Host (H2T Mode)...')
	else:
		info('Running from ISO (USB Mode)...')


def _bootstrap() -> int:
	if Os.get_env('ARCHINSTALL_DEPS_FETCHED'):
		info('Already bootstrapped...')
		return 0
	try:
		info('Fetching deps...')
		Pacman.run(f'-S --needed --noconfirm {" ".join(hard_depends)}', peek_output=True)
		# refresh python last then re-exec to load new libraries
		Pacman.run('-S --needed --noconfirm python', peek_output=True)
	except Exception:
		return 1
	# mark in current env as bootstraped
	# avoid infinite reloads
	Os.set_env('ARCHINSTALL_DEPS_FETCHED', '1')
	info('Reloading python...')
	reload_python()
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


hard_depends = ('python-pyparted',)

# note we want to load all these after bootstrap
from .lib.args import (
	ROOTLESS_SCRIPTS,
	ArchConfigHandler,
	Arguments,
	get_arch_config_handler,
)
from .lib.disk.utils import disk_layouts


def _log_sys_info(args: Arguments) -> None:
	debug(f'Hardware model detected: {SysInfo.sys_vendor()} {SysInfo.product_name()}; UEFI mode: {SysInfo.has_uefi()}')
	debug(f'Processor model detected: {SysInfo.cpu_model()}')
	debug(f'Memory statistics: {SysInfo.mem_total()} total installed')
	debug(f'Virtualization detected is VM: {SysInfo.is_vm()}')
	debug(f'Graphics devices detected: {SysInfo._graphics_devices().keys()}')
	if args.debug:
		debug(f'Disk states before installing:\n{disk_layouts()}')


def _run_script(script: str) -> None:
	importlib.import_module(f'archinstall.scripts.{script}')


def main(script: str, handler: ArchConfigHandler) -> int:
	"""
	Usually ran straight as a module: python -m archinstall or compiled as a package.
	In any case we will be attempting to load the provided script to be run from the scripts/ folder
	"""
	# handle global help
	args = handler.args
	if '-h' in sys.argv or '--help' in sys.argv:
		handler.print_help()
		return 0

	if not is_root():
		print(tr('Archinstall {script} requires root privileges to run. See --help for more.').format(script=script))
		return 1

	# fixes #4149 by passing args properly to subscripts
	handler.pass_args_to_subscript()
	# usually 'guided' from default lib/args
	_run_script(script)
	# note only log once install started
	_log_sys_info(args)

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


def run_as_a_module() -> int:
	handler = get_arch_config_handler()

	if handler.args.debug:
		output.log_level = logging.DEBUG

	# handle scripts that don't need root early before main(script)
	# anything else is assumed to need root
	script = handler.get_script()
	if script in ROOTLESS_SCRIPTS:
		handler.pass_args_to_subscript()
		_run_script(script)
		return 0

	rc = 0
	exc = None

	try:
		if rc := _prepare():
			return rc
		# now run any script that does need root
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


__all__ = [
	'FormattedOutput',
	'Language',
	'Pacman',
	'SysInfo',
	'Tui',
	'debug',
	'disk_layouts',
	'error',
	'info',
	'log',
	'translation_handler',
	'warn',
]
