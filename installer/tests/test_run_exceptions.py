import os
import subprocess
import sys

import pytest

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.general import run


def test_run_failure_caught_by_either_vocabulary() -> None:
	# both exec paths must raise one type: handlers written against
	# SysCommand's SysCallError and against CalledProcessError each
	# have to catch a run() failure (firewall.py regression)
	with pytest.raises(SysCallError) as exc:
		run(['false'])

	err = exc.value
	assert isinstance(err, subprocess.CalledProcessError)
	# SysCommand vocabulary
	assert err.exit_code == 1
	assert isinstance(err.worker_log, bytes)
	assert 'abnormal exit code' in str(err)
	# CalledProcessError vocabulary
	assert err.returncode == 1
	assert err.cmd == ['false']


def test_run_failure_carries_stderr() -> None:
	with pytest.raises(SysCallError) as exc:
		run(['python3', '-c', 'import sys; sys.exit(print("boom", file=sys.stderr) or 3)'])

	err = exc.value
	assert err.returncode == 3
	assert b'boom' in err.stderr
	assert b'boom' in err.worker_log


def test_run_child_stdin_is_readable() -> None:
	# nohup reopens stdin as a write-only /dev/null; arch-chroot -S passes
	# fd 0 on to systemd-run --pipe and systemd refuses a write-only fd as
	# StandardInput. run() must not inherit whatever the launcher left there.
	saved = os.dup(0)
	try:
		os.dup2(os.open(os.devnull, os.O_WRONLY), 0)
		run([sys.executable, '-c', 'import os; os.read(0, 1)'])
	finally:
		os.dup2(saved, 0)
		os.close(saved)


def test_run_input_still_reaches_child() -> None:
	out = run(['cat'], input_data=b'ping')
	assert out.stdout == b'ping'
