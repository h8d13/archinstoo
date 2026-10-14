# scripts that install onto the running system (target '/') would land in
# BOOT's throwaway root and vanish with it, so they are refused there

import pytest

import archinstoo
from archinstoo.lib.utils.env import Os


@pytest.mark.parametrize(
	('script', 'bootstrap', 'blocked'),
	[
		('packages', True, True),
		# on an installed Fedora, '/' is the real system
		('packages', False, False),
		# disk scripts install into a separate target either way
		('guided', True, False),
		(None, True, False),
	],
)
def test_bootstrap_blocked(monkeypatch: pytest.MonkeyPatch, script: str | None, bootstrap: bool, blocked: bool) -> None:
	monkeypatch.setattr(Os, 'running_from_bootstrap', staticmethod(lambda: bootstrap))

	assert archinstoo._is_bootstrap_blocked(script) is blocked
