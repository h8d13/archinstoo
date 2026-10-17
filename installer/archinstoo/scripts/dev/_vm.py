import os
from pathlib import Path

# the dev VM keeps its disk, sockets and logs in the repo root (git-ignored):
# installer/archinstoo/scripts/dev/_vm.py is four levels below it
ROOT = Path(__file__).resolve().parents[4]
SERIAL = ROOT / '.dev-serial.sock'
MONITOR = ROOT / '.dev-monitor.sock'
LOG = ROOT / '.dev-serial.log'
CAPTURE = ROOT / '.dev-capture.log'
PIDFILE = ROOT / '.dev-vm.pid'


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
