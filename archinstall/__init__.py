"""Arch Linux installer - guided, templates etc."""

import importlib
import os
import sys
import traceback

from archinstall.lib.args import arch_config_handler
from archinstall.lib.disk.utils import disk_layouts
from archinstall.lib.networking import ping

from .lib.general import running_from_host
from .lib.hardware import SysInfo
from .lib.output import FormattedOutput, debug, error, info, log, warn
from .lib.pacman import Pacman
from .lib.translationhandler import Language, tr, translation_handler
from .tui.curses_menu import Tui

hard_depends = (
	'python-pyparted',
	'python-pydantic',
	'python-annotated-types',
	'python-pydantic-core',
	'python-typing_extensions',
	'python-typing-inspection',
)


def _log_sys_info() -> None:
	# Log various information about hardware before starting the installation. This might assist in troubleshooting
	debug(f'Hardware model detected: {SysInfo.sys_vendor()} {SysInfo.product_name()}; UEFI mode: {SysInfo.has_uefi()}')
	debug(f'Processor model detected: {SysInfo.cpu_model()}')
	debug(f'Memory statistics: {SysInfo.mem_total()} total installed')
	debug(f'Virtualization detected is VM: {SysInfo.is_vm()}')
	debug(f'Graphics devices detected: {SysInfo._graphics_devices().keys()}')

	# For support reasons, we'll log the disk layout pre installation to match against post-installation layout
	debug(f'Disk states before installing:\n{disk_layouts()}')


def _check_online() -> None:
	try:
		ping('1.1.1.1')
	except OSError as ex:
		if 'Network is unreachable' in str(ex):
			info('Use iwctl/nmcli to connect manually.')
			sys.exit(0)


def _fetch_deps() -> None:
	if os.environ.get('ARCHINSTALL_DEPS_FETCHED'):
		return
	Pacman.run(f'-Sy --needed --noconfirm {" ".join(hard_depends)}', peek_output=True)
	# Refresh python last then re-exec to load new libraries
	Pacman.run('-Sy --noconfirm python', peek_output=True)

	# Re-exec as module to pick up new Python libraries
	os.environ['ARCHINSTALL_DEPS_FETCHED'] = '1'
	os.execv(sys.executable, [sys.executable, '-m', 'archinstall'] + sys.argv[1:])


def _fetch_arch_db() -> None:
	info('Fetching sync db then hard deps...')
	try:
		Pacman.run('-Sy', peek_output=True)
		_fetch_deps()

	except Exception as e:
		error('Failed to sync package database.')
		if 'could not resolve host' in str(e).lower():
			error('Most likely due to a missing network connection or DNS issue.')

		error('Run archinstall --debug and check /var/log/archinstall/install.log for details.')

		debug(f'Failed to sync package database: {e}')
		sys.exit(1)


def main() -> int:
	"""
	Usually ran straight as a module: python -m archinstall or compiled as a package.
	In any case we will be attempting to load the provided script to be run from the scripts/ folder
	"""
	if '--help' in sys.argv or '-h' in sys.argv:
		arch_config_handler.print_help()
		return 0

	if os.getuid() != 0:
		print(tr('Archinstall requires root privileges to run. See --help for more.'))
		return 1

	_log_sys_info()

	if not arch_config_handler.args.offline:
		_check_online()
		_fetch_arch_db()

	if running_from_host():
		# log which mode we are using
		debug('Running from Host (H2T Mode)...')
	else:
		debug('Running from ISO (Live Mode)...')

	script = arch_config_handler.get_script()

	mod_name = f'archinstall.scripts.{script}'
	# by loading the module we'll automatically run the script
	importlib.import_module(mod_name)

	return 0


def run_as_a_module() -> None:
	rc = 0
	exc = None

	try:
		rc = main()
	except Exception as e:
		exc = e
	finally:
		# restore the terminal to the original state
		Tui.shutdown()

		if exc:
			err = ''.join(traceback.format_exception(exc))
			error(err)

			text = (
				f'Archinstall experienced the above error. If you think this is a bug, please report it to\n'
				f'{arch_config_handler.config.bug_report_url} and include the log file "/var/log/archinstall/install.log".\n\n'
				f"Hint: To extract the log from a live ISO \ncurl -F 'file=@/var/log/archinstall/install.log' https://0x0.st\n"
			)

			warn(text)
			rc = 1

		sys.exit(rc)


__all__ = [
	'FormattedOutput',
	'Language',
	'Pacman',
	'SysInfo',
	'Tui',
	'arch_config_handler',
	'debug',
	'disk_layouts',
	'error',
	'info',
	'log',
	'translation_handler',
	'warn',
]
