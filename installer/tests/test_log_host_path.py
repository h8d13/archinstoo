# under BOOT the installer runs chrooted: its /root/... log sits under BOOT's
# root on the host, and the path printed has to be the one the user can open

from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.output import Logger

if TYPE_CHECKING:
	import pytest


def test_boot_names_the_host_path(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setenv('A2_BOOT_ROOT', '/tmp/F2-boot/root.x86_64')
	logger = Logger(Path('/root/.local/state/archinstoo'))

	assert logger.host_path == Path('/tmp/F2-boot/root.x86_64/root/.local/state/archinstoo/install.log')
	assert logger.path == Path('/root/.local/state/archinstoo/install.log')


def test_host_run_keeps_its_path(monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.delenv('A2_BOOT_ROOT', raising=False)
	logger = Logger(Path('/root/.local/state/archinstoo'))

	assert logger.host_directory == logger.directory
