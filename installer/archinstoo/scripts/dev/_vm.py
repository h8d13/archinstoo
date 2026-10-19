import os
from pathlib import Path

from archinstoo.lib.output import error

# the dev VM keeps its disk, sockets and logs in the repo root (git-ignored):
# installer/archinstoo/scripts/dev/_vm.py is four levels below it
ROOT = Path(__file__).resolve().parents[4]
SERIAL = ROOT / '.dev-serial.sock'
MONITOR = ROOT / '.dev-monitor.sock'
LOG = ROOT / '.dev-serial.log'
CAPTURE = ROOT / '.dev-capture.log'
PIDFILE = ROOT / '.dev-vm.pid'
# the --console the running VM was started with
STATE = ROOT / '.dev-vm.state'

VM = './RUN --script dev.vm'
CONSOLES = ('window', 'serial', 'tty')


def vm_pid() -> int | None:
	try:
		pid = int(PIDFILE.read_text().strip())
	except FileNotFoundError, ValueError:
		return None
	try:
		os.kill(pid, 0)
	except OSError:
		return None
	return pid


def vm_console() -> str:
	try:
		console = STATE.read_text().strip()
	except FileNotFoundError:
		return 'unknown'
	return console if console in CONSOLES else 'unknown'


def need_serial() -> None:
	# everything that types into ttyS0 or the monitor needs a --console serial VM
	if not (pid := vm_pid()):
		error(
			f'No VM running. Start one headless: {VM} fresh '
			'--console serial (or keep/boot)'
		)
		raise SystemExit(1)
	if (console := vm_console()) != 'serial':
		error(
			f'VM pid {pid} runs with --console {console}: no '
			'serial socket to drive.'
		)
		error(
			f'Restart it headless: {VM} quit && {VM} keep '
			'--console serial (or boot)'
		)
		raise SystemExit(1)
