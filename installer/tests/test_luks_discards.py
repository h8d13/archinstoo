import subprocess
from pathlib import Path

import pytest

from archinstoo.lib.disk import luks
from archinstoo.lib.models.users import Password


@pytest.fixture
def captured_argv(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
	calls: list[list[str]] = []

	def _run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
		calls.append(cmd)
		return subprocess.CompletedProcess(cmd, 0, b'', b'')

	monkeypatch.setattr(luks, 'run', _run)
	monkeypatch.setattr(luks.Luks2, 'is_unlocked', lambda _self: True)
	monkeypatch.setattr(luks, 'SysCommand', lambda *_a, **_k: None)
	return calls


def _unlock(captured_argv: list[list[str]]) -> list[str]:
	handler = luks.Luks2(
		Path('/dev/vda2'),
		mapper_name='root',
		password=Password(plaintext='test'),
	)
	handler.unlock()
	return captured_argv[-1]


def test_unlock_persists_allow_discards(captured_argv: list[list[str]]) -> None:
	# dm-crypt drops discards by default, so fstrim.timer trims nothing on an
	# encrypted root and btrfs' own discards are dropped too. --persistent
	# writes the flag into the LUKS2 header once, and every later unlock
	# inherits it without crypttab or a kernel parameter.
	argv = _unlock(captured_argv)

	assert '--allow-discards' in argv
	assert '--persistent' in argv


def test_unlock_still_pins_luks2(captured_argv: list[list[str]]) -> None:
	# --persistent is only meaningful on LUKS2; the type must stay pinned
	argv = _unlock(captured_argv)
	assert argv[argv.index('--type') + 1] == 'luks2'
