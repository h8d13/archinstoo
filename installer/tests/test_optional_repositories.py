from typing import TYPE_CHECKING

import pytest

from archinstoo.lib import hardware
from archinstoo.lib.linux_path import LPath
from archinstoo.lib.models.packages import Repository
from archinstoo.lib.pm import config as pm_config
from archinstoo.lib.pm.config import PacmanConfig
from archinstoo.lib.pm.mirrors import optional_repositories

if TYPE_CHECKING:
	from pathlib import Path


@pytest.mark.parametrize(
	('arch', 'offered'),
	[
		('x86_64', [Repository.Multilib, Repository.MultilibTesting, Repository.CoreTesting, Repository.ExtraTesting]),
		('aarch64', [Repository.CoreTesting, Repository.ExtraTesting]),
	],
)
def test_optional_repositories_follow_the_port(monkeypatch: pytest.MonkeyPatch, arch: str, offered: list[Repository]) -> None:
	monkeypatch.setattr(hardware.SysInfo, 'arch', staticmethod(lambda: arch))

	assert optional_repositories() == offered


def test_forge_is_not_a_custom_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# the Arch Ports ISO conf: forge sits next to core/extra as a port repo,
	# only the ISO builder's own repo is custom
	conf = tmp_path / 'pacman.conf'
	conf.write_text(
		"""[options]
SigLevel = Required DatabaseOptional

[ironrobin-aarch64]
Server = https://codeberg.org/ironrobin/aarch64/releases/download/packages

[forge]
Server = https://arch-linux-repo.drzee.net/arch/$repo/os/$arch

[core]
Server = https://arch-linux-repo.drzee.net/arch/$repo/os/$arch
"""
	)
	monkeypatch.setattr(pm_config, 'PACMAN_CONF', LPath(conf))

	assert [r.name for r in PacmanConfig.get_existing_custom_repos()] == ['ironrobin-aarch64']
