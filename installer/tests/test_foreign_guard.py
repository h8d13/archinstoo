# Before bootstrap, the script decides whether the running system may be
# touched at all and which half of the deps it gets. A wrong call is silent:
# the script still runs, on a host it should have refused or under-provisioned.

import pytest

import archinstoo
from archinstoo.lib.utils.env import Os


@pytest.mark.parametrize(
	('script', 'distro_id', 'on_iso', 'bootstrap', 'blocked'),
	[
		# running-system script on a non-Arch root: the case the guard exists for
		('packages', 'debian', False, False, True),
		('packages', 'alpine', False, False, True),
		# same script where target '/' really is Arch, host or ISO
		('packages', 'arch', False, False, False),
		('packages', '', True, False, False),
		# Arch too, but distros/BOOT's throwaway root
		('packages', 'arch', False, True, True),
		# disk scripts pacstrap a separate target, foreign host or not
		('guided', 'debian', False, False, False),
		('guided', 'arch', False, True, False),
		(None, 'debian', False, False, False),
	],
)
def test_foreign_blocked(
	monkeypatch: pytest.MonkeyPatch,
	script: str | None,
	distro_id: str,
	on_iso: bool,
	bootstrap: bool,
	blocked: bool,
) -> None:
	monkeypatch.setattr('platform.freedesktop_os_release', lambda: {'ID': distro_id})
	monkeypatch.setattr(Os, 'running_from_host', staticmethod(lambda: not on_iso))
	monkeypatch.setattr(Os, 'running_from_bootstrap', staticmethod(lambda: bootstrap))

	assert archinstoo._is_foreign_blocked(script) is blocked


@pytest.mark.parametrize('bootstrap', [False, True])
def test_disk_depends_only_on_bootstrap(monkeypatch: pytest.MonkeyPatch, bootstrap: bool) -> None:
	# Arch host/ISO ship the disk tools; the BOOT tarball root ships only python
	monkeypatch.setattr(Os, 'running_from_bootstrap', staticmethod(lambda: bootstrap))
	depends = set(archinstoo._depends())

	assert set(archinstoo.base_depends) <= depends
	assert (set(archinstoo.disk_depends) <= depends) is bootstrap
	assert not set(archinstoo.base_depends) & set(archinstoo.disk_depends)
