# Failed fetches raise FetchError, so callers falling back on a dead network
# do not also swallow unrelated ValueErrors. The lvm retry waits out a report
# that is still empty, and lets a malformed one surface instead of looping.

import json
from typing import TYPE_CHECKING
from urllib.error import URLError

import pytest

from archinstoo.lib.disk import lvm
from archinstoo.lib.exceptions import FetchError
from archinstoo.lib.utils import net

if TYPE_CHECKING:
	from pathlib import Path


def _unreachable(*_: object, **__: object) -> None:
	raise URLError('no route to host')


def test_fetch_failure_is_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(net, 'urlopen', _unreachable)

	with pytest.raises(FetchError):
		net.fetch_data_from_url('https://example.org')


def test_download_failure_is_fetch_error(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	monkeypatch.setattr(net, 'urlopen', _unreachable)

	with pytest.raises(FetchError):
		net.download_file_from_url('https://example.org/pkg', tmp_path / 'pkg')


def test_non_http_scheme_is_fetch_error() -> None:
	with pytest.raises(FetchError):
		net.fetch_data_from_url('file:///etc/shadow')


class _Report:
	def __init__(self, lv: list[dict[str, str]]) -> None:
		self._data = json.dumps({'report': [{'lv': lv}]})

	def decode(self) -> str:
		return self._data


def _lvs(monkeypatch: pytest.MonkeyPatch, lv: list[dict[str, str]]) -> list[float]:
	sleeps: list[float] = []
	monkeypatch.setattr(lvm, 'SysCommand', lambda _: _Report(lv))
	monkeypatch.setattr('time.sleep', sleeps.append)
	return sleeps


def test_lvm_retries_empty_report(monkeypatch: pytest.MonkeyPatch) -> None:
	sleeps = _lvs(monkeypatch, [])

	assert lvm.lvm_vol_info('root') is None
	assert len(sleeps) == 99


def test_lvm_malformed_report_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
	sleeps = _lvs(
		monkeypatch,
		[{'lv_name': 'root', 'vg_name': 'vg', 'lv_size': 'garbage'}],
	)

	with pytest.raises(ValueError, match='invalid literal'):
		lvm.lvm_vol_info('root')
	assert not sleeps
