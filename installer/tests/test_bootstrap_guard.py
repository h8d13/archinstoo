# Before bootstrap, the script decides whether the running system may be
# touched at all and which half of the deps it gets. A wrong call is silent:
# the script still runs, on a host it should have refused or under-provisioned.

import pytest

import archinstoo
from archinstoo import deps
from archinstoo.lib.pm.pacman import Pacman
from archinstoo.lib.utils.host import Host


@pytest.mark.parametrize(
	('script', 'bootstrap', 'blocked'),
	[
		# running-system script in the throwaway bootstrap root: the case
		# the guard exists for
		('packages', True, True),
		# same script where target '/' really is the system, host or ISO
		('packages', False, False),
		# disk scripts pacstrap a separate target either way
		('guided', True, False),
		(None, True, False),
	],
)
def test_bootstrap_blocked(
	monkeypatch: pytest.MonkeyPatch,
	script: str | None,
	bootstrap: bool,
	blocked: bool,
) -> None:
	monkeypatch.setattr(
		Host, 'running_from_bootstrap', staticmethod(lambda: bootstrap)
	)

	assert archinstoo._is_bootstrap_blocked(script) is blocked


@pytest.mark.parametrize('distro_id', ['debian', 'alpine', 'fedora'])
def test_foreign_host_refused(monkeypatch: pytest.MonkeyPatch, distro_id: str) -> None:
	# no pacman config or keyring off Arch: pointed at --script
	# bootstrap, nothing synced
	calls: list[str] = []
	monkeypatch.setattr(
		'platform.freedesktop_os_release', lambda: {'ID': distro_id}
	)
	monkeypatch.setattr(Host, 'running_from_host', staticmethod(lambda: True))
	monkeypatch.setattr(Host, 'running_from_bootstrap', staticmethod(lambda: False))
	monkeypatch.setattr(archinstoo, 'is_root', lambda: True)
	monkeypatch.setattr(archinstoo, '_log_env_info', lambda: None)
	monkeypatch.setattr(
		Pacman, 'run', staticmethod(lambda args, **_: calls.append(args))
	)

	assert archinstoo._prepare(offline=False) == 1
	assert calls == []


@pytest.mark.parametrize('bootstrap', [False, True])
def test_disk_depends_only_on_bootstrap(
	monkeypatch: pytest.MonkeyPatch, bootstrap: bool
) -> None:
	# Arch host/ISO ship the disk tools; --script bootstrap
	# installs both into its root
	monkeypatch.setattr(
		Host, 'running_from_bootstrap', staticmethod(lambda: bootstrap)
	)
	depends = set(archinstoo._depends())

	assert set(deps.BASE) <= depends
	assert (set(deps.DISK) <= depends) is bootstrap
	assert not set(deps.BASE) & set(deps.DISK)
