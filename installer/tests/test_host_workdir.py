# On an Arch host the run edits copies of pacman.conf and the mirrorlist, so
# the host's own files are never written.
from typing import TYPE_CHECKING

import pytest

from archinstoo.lib.linux_path import LPath
from archinstoo.lib.pm import pacman
from archinstoo.lib.pm.pacman import MIRRORLIST, PACMAN_CONF, live
from archinstoo.lib.utils.host import Host

if TYPE_CHECKING:
	from collections.abc import Iterator
	from pathlib import Path

# conftest stubs the module attribute, this is the real one
_host_workdir = pacman._host_workdir

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

	_host_workdir.cache_clear()
	monkeypatch.setattr(pacman, '_host_workdir', _host_workdir)
	monkeypatch.setattr(pacman, 'PACMAN_CONF', LPath(etc / PACMAN_CONF.name))
	monkeypatch.setattr(pacman, 'MIRRORLIST', LPath(etc / MIRRORLIST.name))
	monkeypatch.setattr(Host, 'running_from_arch_host', staticmethod(lambda: True))
	yield etc
	_host_workdir.cache_clear()


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
