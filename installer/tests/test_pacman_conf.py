# The installed system's pacman.conf is rendered from PacmanConfiguration, not
# copied from the ISO that ran the installer, so a vanilla and a customised ISO
# produce the same target conf for the same config.

from typing import TYPE_CHECKING

import pytest

from archinstoo.lib.linux_path import LPath
from archinstoo.lib.models.mirrors import CustomRepository, PacmanConfiguration, SignCheck, SignOption
from archinstoo.lib.models.packages import Repository
from archinstoo.lib.pm import config as pm_config
from archinstoo.lib.pm.config import PacmanConfig

if TYPE_CHECKING:
	from pathlib import Path

# what pacstrap leaves in the target: the pacman package's own conf
_STOCK_CONF = """\
[options]
HoldPkg = pacman glibc
#Color
#VerbosePkgLists
ParallelDownloads = 5

[core]
Include = /etc/pacman.d/mirrorlist

[extra]
Include = /etc/pacman.d/mirrorlist

#[multilib]
#Include = /etc/pacman.d/mirrorlist
"""

# what a customised ISO runs with, none of which the target should inherit
_ISO_CONF = _STOCK_CONF.replace('#Color', 'Color').replace('ParallelDownloads = 5', 'ParallelDownloads = 5\nILoveCandy')

_CACHE_REPO = CustomRepository('isocache', 'file:///run/archiso/cache', SignCheck.Never, SignOption.TrustAll)
_NET_REPO = CustomRepository('cachyos', 'https://mirror.cachyos.org/repo/x86_64/cachyos', SignCheck.Required, SignOption.TrustedOnly)


def _config() -> PacmanConfiguration:
	return PacmanConfiguration(
		optional_repositories=[Repository.Multilib],
		custom_repositories=[_CACHE_REPO, _NET_REPO],
		pacman_options=['VerbosePkgLists'],
		parallel_downloads=10,
	)


@pytest.fixture
def target(tmp_path: Path) -> Path:
	conf = tmp_path / 'etc/pacman.conf'
	conf.parent.mkdir(parents=True)
	conf.write_text(_STOCK_CONF)
	return tmp_path


def test_target_conf_comes_from_the_config(target: Path) -> None:
	PacmanConfig.apply_config(_config(), target)

	written = (target / 'etc/pacman.conf').read_text()
	assert '\n[multilib]\nInclude' in written, 'optional repository not enabled'
	assert '\nVerbosePkgLists\n' in written, 'requested option not enabled'
	assert 'ParallelDownloads = 10' in written
	assert '[cachyos]' in written


def test_target_conf_inherits_nothing_from_the_iso(target: Path) -> None:
	# _ISO_CONF is what the live system runs with; the target is written from
	# its own stock conf plus the config, so none of it can cross over
	assert 'ILoveCandy' in _ISO_CONF

	PacmanConfig.apply_config(_config(), target)

	written = (target / 'etc/pacman.conf').read_text()
	assert 'ILoveCandy' not in written, 'the ISO conf leaked into the target'
	assert '\nColor\n' not in written, 'the ISO conf leaked into the target'


def test_file_url_repo_never_reaches_the_target(target: Path) -> None:
	# an ISO-local cache path does not exist after reboot
	PacmanConfig.apply_config(_config(), target)

	assert '[isocache]' not in (target / 'etc/pacman.conf').read_text()


def test_file_url_repo_still_serves_the_live_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	live = tmp_path / 'pacman.conf'
	live.write_text(_STOCK_CONF)
	monkeypatch.setattr(pm_config, 'PACMAN_CONF', LPath(live))

	PacmanConfig.apply_config(_config(), None)

	written = live.read_text()
	assert '[isocache]' in written
	assert written.index('[isocache]') < written.index('[core]'), 'cache must outrank the network repos'
