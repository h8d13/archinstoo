# --script bootstrap: the host side before archinstoo runs inside the root.
# Each case is one that broke or would break silently in a VM run.

import subprocess
from pathlib import Path

import pytest

import archinstoo
from archinstoo import deps
from archinstoo.lib import bootstrap
from archinstoo.lib.cli import bootstrap_argv
from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.utils.host import Host


def _fake_bin(bin_dir: Path, name: str, body: str) -> None:
	tool = bin_dir / name
	tool.write_text(f'#!/bin/sh\n{body}\n')
	tool.chmod(0o755)


@pytest.mark.parametrize(('deptest_exit', 'synced'), [(0, False), (127, True)])
def test_deps_only_synced_when_missing(
	tmp_path: Path, deptest_exit: int, synced: bool
) -> None:
	# the root is reused across runs: a rerun with every dep in must not sync.
	# Only what -T reports goes to -Syu, the tarball's own warn 'up to date'
	calls = tmp_path / 'pacman.args'
	missing = 'python\nefibootmgr' if synced else ''
	_fake_bin(
		tmp_path,
		'pacman',
		f'case "$*" in *-T*) printf "{missing}"; exit {deptest_exit};; esac\n'
		f'echo "$@" > {calls}',
	)

	subprocess.run(  # noqa: S603 - the bootstrap's own command
		['/bin/sh', '-c', bootstrap.install_deps_cmd()],
		env={'PATH': str(tmp_path)},
		check=True,
	)

	assert calls.exists() is synced
	if synced:
		assert calls.read_text().split() == [
			'-Syu',
			'--noconfirm',
			'python',
			'efibootmgr',
		]


def test_python_and_both_dep_sets_inside() -> None:
	# the tarball ships no python-pyparted or disk tools, the ISO's split
	# (base only) does not apply in the root
	assert bootstrap.DEPENDS[0] == 'python'
	assert set(deps.BASE) | set(deps.DISK) <= set(bootstrap.DEPENDS)


@pytest.mark.parametrize(
	('argv', 'inner', 'extra'),
	[
		# what follows -- reaches the root as given
		(
			[
				'--script',
				'bootstrap',
				'--',
				'--script',
				'minimal',
				'--silent',
			],
			['--', '--script', 'minimal', '--silent'],
			[],
		),
		(['--script=bootstrap', '--debug'], ['--'], []),
		# the script's own help, before anything is fetched
		(['--script', 'bootstrap', '-h'], ['-h', '--'], []),
		# parsed by the host run and never forwarded
		(
			[
				'--script',
				'bootstrap',
				'--silent',
				'--',
				'--script',
				'guided',
			],
			['--', '--script', 'guided'],
			['--silent'],
		),
	],
)
def test_args_after_dashdash(
	argv: list[str], inner: list[str], extra: list[str]
) -> None:
	assert bootstrap_argv(argv) == (inner, extra)


def test_misplaced_args_refused(monkeypatch: pytest.MonkeyPatch) -> None:
	ran: list[str] = []
	monkeypatch.setattr(
		'sys.argv', ['archinstoo', '--script', 'bootstrap', '--silent']
	)
	monkeypatch.setattr(Host, 'running_from_bootstrap', staticmethod(lambda: False))
	monkeypatch.setattr(archinstoo, '_run_script', ran.append)

	assert archinstoo._run_bootstrap() == 1
	assert ran == []


def test_checksum(tmp_path: Path) -> None:
	tarball = tmp_path / 'archlinux-bootstrap-x86_64.tar.zst'
	tarball.write_bytes(b'tarball')
	sums = tmp_path / 'sha256sums.txt'

	sums.write_text(f'{bootstrap.sha256(tarball)}  {tarball.name}\n')
	bootstrap.verify_sum(tarball, sums)

	sums.write_text(f'{"0" * 64}  {tarball.name}\n')
	with pytest.raises(bootstrap.BootError, match='does not match'):
		bootstrap.verify_sum(tarball, sums)

	sums.write_text(f'{"0" * 64}  archlinux-x86_64.iso\n')
	with pytest.raises(bootstrap.BootError, match='not listed'):
		bootstrap.verify_sum(tarball, sums)


@pytest.mark.parametrize('host_mnt_mounted', [True, False])
def test_root_self_bind_private_first(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path, host_mnt_mounted: bool
) -> None:
	# a shared self-bind (/tmp is shared on the ISO) copied every mount below
	# it into the parent, where teardown never looked: the host's layout
	# stayed mounted twice
	mounts: list[tuple[str, ...]] = []
	(tmp_path / 'root/etc').mkdir(parents=True)
	monkeypatch.setattr(bootstrap, 'ROOT', tmp_path / 'root')
	monkeypatch.setattr(bootstrap, 'mount', lambda *args: mounts.append(args))
	monkeypatch.setattr(
		bootstrap,
		'is_mounted',
		lambda path: host_mnt_mounted and path == Path('/mnt'),
	)

	bootstrap.chroot_setup()

	root = str(tmp_path / 'root')
	assert mounts[0] == ('--bind', '--make-private', root, root)
	# a bare /mnt is the host's root fs: bound in, the target stacked on it
	# and fstab took the host's filesystem for / (a Fedora host's btrfs)
	assert (
		('--rbind', '--make-rslave', '/mnt', f'{root}/mnt') in mounts
	) is host_mnt_mounted


def test_not_nested(monkeypatch: pytest.MonkeyPatch) -> None:
	ran: list[str] = []
	monkeypatch.setattr('sys.argv', ['archinstoo', '--script', 'bootstrap'])
	monkeypatch.setattr(Host, 'running_from_bootstrap', staticmethod(lambda: True))
	monkeypatch.setattr(archinstoo, '_run_script', ran.append)

	assert archinstoo._run_bootstrap() == 1
	assert ran == []


@pytest.mark.parametrize('mounted', [True, False])
def test_teardown_reads_mountinfo(
	monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mounted: bool
) -> None:
	# Path.is_mount() compares st_dev with the parent: the self-bind sits on
	# the same filesystem, read as unmounted, and a run left 23 mounts behind
	calls: list[list[str]] = []

	def fake(cmd: list[str], **_: object) -> None:
		calls.append(cmd)
		if cmd[0] == 'mountpoint' and not mounted:
			raise SysCallError('not a mountpoint', 32)

	monkeypatch.setattr(bootstrap, 'ROOT', tmp_path)
	monkeypatch.setattr(bootstrap, 'SysCommand', fake)

	bootstrap.teardown()

	assert (['umount', '-R', str(tmp_path)] in calls) is mounted
