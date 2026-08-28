import subprocess

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
