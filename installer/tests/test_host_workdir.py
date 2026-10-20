# On an Arch host the run edits copies of pacman.conf and the mirrorlist and
# syncs into its own db, so the host's own pacman state is never written.
import shutil
import subprocess
import time
from typing import TYPE_CHECKING

import pytest

from archinstoo.lib.linux_path import LPath
from archinstoo.lib.pm import pacman, tmpdb
from archinstoo.lib.pm.pacman import (
	MIRRORLIST,
	PACMAN_CONF,
	PACMAN_DB,
	Pacman,
	live,
	workdir,
)
from archinstoo.lib.utils.host import Host

if TYPE_CHECKING:
	from collections.abc import Iterator
	from pathlib import Path


_HOST_CONF = """\
[options]
ParallelDownloads = 5

[core]
Include = {d}/mirrorlist

[extra]
Include   =   {d}/mirrorlist

[cachyos]
Include = {d}/cachyos-mirrorlist

[alarm]
Include = {d}/mirrorlist-arm
"""


@pytest.fixture
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
	etc = tmp_path / 'etc'
	etc.mkdir()
	(etc / PACMAN_CONF.name).write_text(_HOST_CONF.format(d=etc))
	(etc / MIRRORLIST.name).write_text('Server = https://host/$repo\n')

	pacman._workdir.cache_clear()
	monkeypatch.setattr(pacman, 'PACMAN_CONF', LPath(etc / PACMAN_CONF.name))
	monkeypatch.setattr(pacman, 'MIRRORLIST', LPath(etc / MIRRORLIST.name))
	monkeypatch.setattr(Host, 'running_from_arch_host', staticmethod(lambda: True))
	yield etc
	pacman._workdir.cache_clear()


def test_edits_land_in_the_copy(host: Path) -> None:
	conf = live(PACMAN_CONF)
	assert conf.parent != host
	conf.write_text('edited\n')
	live(MIRRORLIST).write_text('edited\n')

	assert (host / PACMAN_CONF.name).read_text() == _HOST_CONF.format(d=host)
	assert (host / MIRRORLIST.name).read_text() == 'Server = https://host/$repo\n'


def test_only_the_arch_mirrorlist_include_moves(host: Path) -> None:
	mirrorlist = live(MIRRORLIST)
	expected = _HOST_CONF.format(d=host).replace(
		f'Include = {host}/mirrorlist\n', f'Include = {mirrorlist}\n'
	)
	expected = expected.replace(
		f'Include   =   {host}/mirrorlist\n', f'Include   =   {mirrorlist}\n'
	)

	assert live(PACMAN_CONF).read_text() == expected
	assert mirrorlist.read_text() == 'Server = https://host/$repo\n'


def test_copy_is_taken_once(host: Path) -> None:
	live(PACMAN_CONF).write_text('edited\n')
	assert live(PACMAN_CONF).read_text() == 'edited\n'


def test_iso_edits_etc(host: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(Host, 'running_from_arch_host', staticmethod(lambda: False))
	assert live(PACMAN_CONF) == PACMAN_CONF


def test_sync_db_is_the_runs(host: Path) -> None:
	db = live(PACMAN_DB)
	assert db.parent == workdir()
	assert db.is_dir()


def _lock_waits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[float]:
	# a held lock in the host db; sleep() releases it, so a wait is one call
	db = tmp_path / 'var/lib/pacman'
	db.mkdir(parents=True)
	(db / 'db.lck').write_text('')
	monkeypatch.setattr(pacman, 'PACMAN_DB', LPath(db))
	monkeypatch.setattr(pacman, 'SysCommand', lambda *_a, **_kw: None)
	waits: list[float] = []

	def sleep(secs: float) -> None:
		waits.append(secs)
		(db / 'db.lck').unlink()

	monkeypatch.setattr(time, 'sleep', sleep)
	return waits


def test_host_lock_does_not_block_the_run(
	host: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
	waits = _lock_waits(monkeypatch, tmp_path)
	Pacman.run('-Sy')
	assert waits == []


def test_iso_waits_on_the_lock(
	host: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
	monkeypatch.setattr(Host, 'running_from_arch_host', staticmethod(lambda: False))
	waits = _lock_waits(monkeypatch, tmp_path)
	Pacman.run('-Sy')
	assert waits == [0.25]


def test_host_keyring_is_never_reset(
	host: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	calls: list[object] = []
	monkeypatch.setattr(pacman, 'SysCommand', lambda *a, **_: calls.append(a))
	monkeypatch.setattr(shutil, 'rmtree', calls.append)

	assert Pacman.reset_keyring() is False
	assert calls == []


def test_files_db_lives_in_the_run(host: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	calls: list[list[str]] = []

	def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
		calls.append(argv)
		return subprocess.CompletedProcess(argv, 1, '', '')

	monkeypatch.setattr(tmpdb, '_run', run)
	db = tmpdb.TmpDB(('core',))
	db.sync_files()

	assert db.root.parent == workdir()
	# servers come from the run's conf, menu edits included
	assert calls[0][:3] == ['pacman-conf', '--config', str(live(PACMAN_CONF))]


def test_strap_leaves_syncing_to_pacstrap(
	host: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
	commands: list[str] = []
	monkeypatch.setattr(pacman, 'SysCommand', lambda cmd, **_: commands.append(cmd))
	monkeypatch.setattr(Pacman, 'run', staticmethod(commands.append))

	Pacman(tmp_path / 'target').strap(['base'])

	target = tmp_path / 'target'
	flags = '--noconfirm --needed'
	assert commands == [f'pacstrap -C {live(PACMAN_CONF)} {target} base {flags}']
