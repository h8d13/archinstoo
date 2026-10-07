import subprocess
from typing import TYPE_CHECKING

import pytest

from archinstoo.lib.pm import tmpdb

if TYPE_CHECKING:
	from pathlib import Path

MIRRORS = ['https://a.example/core/os/x86_64', 'https://b.example/core/os/x86_64']


def _stub(
	monkeypatch: pytest.MonkeyPatch,
	root: bool,
	servers: dict[str, list[str]],
	pacman_rc: int = 0,
	listing: str = '',
) -> list[list[str]]:
	calls: list[list[str]] = []

	def fake_run(argv: list[str]) -> subprocess.CompletedProcess[str]:
		calls.append(argv)
		if argv[0] == 'pacman-conf':
			key, repo = argv[-1], next((a.split('=', 1)[1] for a in argv if a.startswith('--repo=')), None)
			if key == 'Server':
				return subprocess.CompletedProcess(argv, 0 if repo in servers else 1, '\n'.join(servers.get(repo or '', [])), '')
			return subprocess.CompletedProcess(argv, 0, 'PackageRequired\nDatabaseOptional\n', '')
		return subprocess.CompletedProcess(argv, pacman_rc, listing, 'boom' if pacman_rc else '')

	monkeypatch.setattr(tmpdb, '_run', fake_run)
	monkeypatch.setattr(tmpdb, 'is_root', lambda: root)
	return calls


def test_conf_carries_only_the_asked_repos() -> None:
	assert tmpdb.render_conf(['DatabaseOptional'], {'core': MIRRORS}) == (
		'[options]\nArchitecture = auto\nSigLevel = DatabaseOptional\n\n[core]\n'
		'Server = https://a.example/core/os/x86_64\nServer = https://b.example/core/os/x86_64\n'
	)


def test_conf_falls_back_to_arch_siglevel() -> None:
	assert 'SigLevel = Required DatabaseOptional\n' in tmpdb.render_conf([], {'core': MIRRORS})


def test_listing_skips_directories() -> None:
	text = 'amd-ucode usr/lib/firmware/\namd-ucode usr/lib/firmware/amd-ucode/README.zst\nlinux-firmware-ti usr/lib/firmware/ti_3410.fw.zst\n'
	assert tmpdb.parse_files(text) == [
		('amd-ucode', 'usr/lib/firmware/amd-ucode/README.zst'),
		('linux-firmware-ti', 'usr/lib/firmware/ti_3410.fw.zst'),
	]


@pytest.mark.parametrize(('root', 'prefix'), [(True, []), (False, ['fakeroot', '--'])])
def test_sync_stays_in_its_own_dbpath(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: bool, prefix: list[str]) -> None:
	calls = _stub(monkeypatch, root, {'core': MIRRORS})
	db = tmpdb.TmpDB(('core',), root=tmp_path / 'db')

	assert db.sync_files()
	assert calls[-1] == [
		*prefix,
		'pacman',
		'--config',
		str(tmp_path / 'db/pacman.conf'),
		'--dbpath',
		str(tmp_path / 'db'),
		'--logfile',
		'/dev/null',
		'--disable-sandbox-filesystem',
		'-Fy',
	]
	assert 'Server = https://b.example/core/os/x86_64' in db.conf.read_text()


def test_failed_sync_drops_the_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	_stub(monkeypatch, True, {'core': MIRRORS}, pacman_rc=1)
	db = tmpdb.TmpDB(('core',), root=tmp_path / 'db')
	(tmp_path / 'db').mkdir()
	(tmp_path / 'db/db.lck').write_text('')

	assert not db.sync_files()
	assert not (tmp_path / 'db/db.lck').exists()


def test_repo_without_servers_skips_pacman(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	calls = _stub(monkeypatch, True, {})

	assert not tmpdb.TmpDB(('core',), root=tmp_path / 'db').sync_files()
	assert all(c[0] == 'pacman-conf' for c in calls)
	assert not (tmp_path / 'db').exists()


def test_files_reads_the_private_dbpath(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	calls = _stub(monkeypatch, True, {'core': MIRRORS}, listing='linux-firmware-marvell usr/lib/firmware/mrvl/x.bin.zst\n')
	db = tmpdb.TmpDB(('core',), root=tmp_path / 'db')

	assert db.files() == [('linux-firmware-marvell', 'usr/lib/firmware/mrvl/x.bin.zst')]
	assert calls[-1][calls[-1].index('--dbpath') + 1] == str(tmp_path / 'db')
