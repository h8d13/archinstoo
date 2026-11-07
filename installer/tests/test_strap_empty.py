# Profiles hand strap() their package lists as they are, and some are empty:
# the Wayland display server needs none (its compositor pulls its own), so a
# Plasma install ran pacman -S with no targets and failed.

from pathlib import Path

import pytest

from archinstoo.lib.pm import pacman as pacman_mod
from archinstoo.lib.pm.pacman import Pacman


@pytest.mark.parametrize('target', [Path('/'), Path('/mnt')])
def test_empty_package_list_runs_nothing(
	monkeypatch: pytest.MonkeyPatch, target: Path
) -> None:
	ran: list[str] = []
	monkeypatch.setattr(pacman_mod, 'SysCommand', lambda cmd, **_: ran.append(cmd))

	Pacman(target).strap([])

	assert ran == []
