# _prepare runs before argparse: it decides whether this host can install at
# all (the BOOT root or a Fedora host) and checks, never installs, the deps.

import ast
from pathlib import Path

import pytest

import archinstoo
from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.utils.env import Os


@pytest.mark.parametrize(
	('distro_id', 'bootstrap', 'fedora_host'),
	[
		('fedora', False, True),
		# BOOT's root is Fedora too, but throwaway
		('fedora', True, False),
		('arch', False, False),
	],
)
def test_fedora_host(monkeypatch: pytest.MonkeyPatch, distro_id: str, bootstrap: bool, fedora_host: bool) -> None:
	monkeypatch.setattr('platform.freedesktop_os_release', lambda: {'ID': distro_id})
	monkeypatch.setattr(Os, 'running_from_bootstrap', staticmethod(lambda: bootstrap))

	assert Os.running_from_fedora_host() is fedora_host


def _prepare_env(monkeypatch: pytest.MonkeyPatch, *, bootstrap: bool, fedora_host: bool, missing: list[str]) -> None:
	monkeypatch.setattr(archinstoo, 'is_root', lambda: True)
	monkeypatch.setattr(archinstoo, '_log_env_info', lambda: None)
	monkeypatch.setattr(archinstoo, '_check_online', lambda: 0)
	monkeypatch.setattr(archinstoo, '_missing_deps', lambda depends: missing)
	monkeypatch.setattr(Os, 'running_from_bootstrap', staticmethod(lambda: bootstrap))
	monkeypatch.setattr(Os, 'running_from_fedora_host', staticmethod(lambda: fedora_host))


@pytest.mark.parametrize(
	('bootstrap', 'fedora_host', 'missing', 'rc'),
	[
		(True, False, [], 0),
		(False, True, [], 0),
		# reported, never fetched: the host's dnf owns its packages
		(False, True, ['lvm2'], 1),
		# neither: no dnf or rpm database to strap from
		(False, False, [], 1),
	],
)
def test_prepare(monkeypatch: pytest.MonkeyPatch, bootstrap: bool, fedora_host: bool, missing: list[str], rc: int) -> None:
	_prepare_env(monkeypatch, bootstrap=bootstrap, fedora_host=fedora_host, missing=missing)

	assert archinstoo._prepare(offline=False) == rc


def _rpm_exits(monkeypatch: pytest.MonkeyPatch, log: bytes) -> None:
	def run(cmd: list[str], **_: object) -> None:
		raise SysCallError(' '.join(cmd), len(log.splitlines()), worker_log=log)

	monkeypatch.setattr(archinstoo, 'SysCommand', run)


@pytest.mark.parametrize(
	('log', 'missing'),
	[
		(b'git-2.51.0-1.fc44.x86_64\r\nno package provides lvm2\r\nno package provides mdadm\r\n', ['lvm2', 'mdadm']),
		# rpm failing for any other reason says nothing about the deps
		(b'error: cannot open Packages database\r\n', None),
	],
)
def test_missing_deps(monkeypatch: pytest.MonkeyPatch, log: bytes, missing: list[str] | None) -> None:
	_rpm_exits(monkeypatch, log)
	depends = ('git', 'lvm2', 'mdadm')

	if missing is None:
		with pytest.raises(SysCallError):
			archinstoo._missing_deps(depends)
	else:
		assert archinstoo._missing_deps(depends) == missing


def test_boot_installs_what_prepare_checks() -> None:
	# BOOT is stdlib-only and cannot import the list, so it keeps its own:
	# everything _prepare requires has to be in it
	tree = ast.parse((Path(__file__).parents[2] / 'BOOT').read_text())
	boot = next(
		ast.literal_eval(node.value)
		for node in tree.body
		if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'DEPENDS' for t in node.targets)
	)

	assert set(archinstoo.host_depends) <= set(boot)
