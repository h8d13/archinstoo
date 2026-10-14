# luksFormat on Fedora enforces libpwquality; the same verdict is asked of
# pwscore before the disk is touched

import subprocess
from typing import TYPE_CHECKING

from archinstoo.lib.disk import luks

if TYPE_CHECKING:
	import pytest


def _pwscore(monkeypatch: pytest.MonkeyPatch, rc: int, out: str) -> None:
	monkeypatch.setattr('shutil.which', lambda name: '/usr/bin/pwscore')
	monkeypatch.setattr('subprocess.run', lambda *a, **kw: subprocess.CompletedProcess(a, rc, stdout=out, stderr=''))


def test_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
	_pwscore(monkeypatch, 0, '62\n')
	assert luks.passphrase_error('a sound passphrase') is None


def test_rejection_carries_the_reason(monkeypatch: pytest.MonkeyPatch) -> None:
	_pwscore(monkeypatch, 1, 'Password quality check failed:\n The password is shorter than 8 characters\n')
	assert luks.passphrase_error('test') == 'The password is shorter than 8 characters'


def test_no_pwscore_no_policy(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr('shutil.which', lambda name: None)
	assert luks.passphrase_error('x') is None
