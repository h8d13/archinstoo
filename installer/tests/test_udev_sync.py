# udev waits under distros/BOOT: settle, queue poll, lsblk retry.
# A fake clock keeps the deadlines testable without sleeping.

from pathlib import Path
from types import SimpleNamespace

import pytest

from archinstoo.lib.disk import device_handler
from archinstoo.lib.disk.device_handler import DeviceHandler
from archinstoo.lib.exceptions import DiskError
from archinstoo.lib.models.device import LsblkInfo

_QUEUE = Path('/run/udev/queue')
_Env = list[dict[str, str] | None]


class _Clock:
	def __init__(self) -> None:
		self.now = 0.0
		self.sleeps = 0

	def monotonic(self) -> float:
		return self.now

	def sleep(self, secs: float) -> None:
		self.sleeps += 1
		self.now += secs


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
	fake = _Clock()
	monkeypatch.setattr(device_handler, 'time', SimpleNamespace(monotonic=fake.monotonic, sleep=fake.sleep))
	return fake


@pytest.fixture
def settle_env(monkeypatch: pytest.MonkeyPatch) -> _Env:
	calls: _Env = []

	def _syscommand(cmd: str, environment_vars: dict[str, str] | None = None, **_: object) -> None:
		assert cmd == 'udevadm settle'
		calls.append(environment_vars)

	monkeypatch.setattr(device_handler, 'SysCommand', _syscommand)
	return calls


def _queue_for(monkeypatch: pytest.MonkeyPatch, busy_checks: int | None) -> list[int]:
	# queue file reads as present for the first busy_checks polls (None: forever)
	seen = [0]
	real_exists = Path.exists

	def _exists(self: Path, *, follow_symlinks: bool = True) -> bool:
		if self != _QUEUE:
			return real_exists(self, follow_symlinks=follow_symlinks)
		seen[0] += 1
		return busy_checks is None or seen[0] <= busy_checks

	monkeypatch.setattr(Path, 'exists', _exists)
	return seen


def test_settle_overrides_chroot_and_skips_idle_queue(clock: _Clock, settle_env: _Env, monkeypatch: pytest.MonkeyPatch) -> None:
	seen = _queue_for(monkeypatch, 0)
	DeviceHandler.udev_sync()
	assert settle_env == [{'SYSTEMD_IN_CHROOT': '0'}]
	assert seen[0] == 1
	assert clock.sleeps == 0


@pytest.mark.usefixtures('settle_env')
def test_queue_poll_waits_until_drained(clock: _Clock, monkeypatch: pytest.MonkeyPatch) -> None:
	seen = _queue_for(monkeypatch, 3)
	DeviceHandler.udev_sync()
	assert seen[0] == 4
	assert clock.sleeps == 3


@pytest.mark.usefixtures('settle_env')
def test_queue_poll_gives_up_at_deadline(clock: _Clock, monkeypatch: pytest.MonkeyPatch) -> None:
	# a wedged host udevd must not hang the install
	_queue_for(monkeypatch, None)
	DeviceHandler.udev_sync()
	assert 10 <= clock.now < 10.1


def _lsblk(uuid: str | None) -> LsblkInfo:
	return LsblkInfo.from_dict(
		{
			'name': 'vdb1',
			'path': '/dev/vdb1',
			'partn': 1,
			'partuuid': '0a1b2c3d-01',
			'uuid': uuid,
		}
	)


def _lsblk_sequence(monkeypatch: pytest.MonkeyPatch, empty_reads: int | None) -> list[int]:
	# uuid stays unset for the first empty_reads calls (None: forever)
	calls = [0]

	def _get(_path: Path) -> LsblkInfo:
		calls[0] += 1
		ready = empty_reads is not None and calls[0] > empty_reads
		return _lsblk('19F1-92A4' if ready else None)

	monkeypatch.setattr(device_handler, 'get_lsblk_info', _get)
	return calls


def _fetch(path: Path) -> LsblkInfo:
	# fetch_part_info never touches self; building a DeviceHandler scans disks
	return DeviceHandler.fetch_part_info(object.__new__(DeviceHandler), path)


def test_fetch_part_info_no_retry_when_ready(clock: _Clock, monkeypatch: pytest.MonkeyPatch) -> None:
	calls = _lsblk_sequence(monkeypatch, 0)
	assert _fetch(Path('/dev/vdb1')).uuid == '19F1-92A4'
	assert calls[0] == 1
	assert clock.sleeps == 0


def test_fetch_part_info_retries_until_uuid(clock: _Clock, monkeypatch: pytest.MonkeyPatch) -> None:
	calls = _lsblk_sequence(monkeypatch, 4)
	assert _fetch(Path('/dev/vdb1')).uuid == '19F1-92A4'
	assert calls[0] == 5


def test_fetch_part_info_raises_after_deadline(clock: _Clock, monkeypatch: pytest.MonkeyPatch) -> None:
	_lsblk_sequence(monkeypatch, None)
	with pytest.raises(DiskError, match='Unable to determine new uuid'):
		_fetch(Path('/dev/vdb1'))
	assert 5 <= clock.now < 5.2
