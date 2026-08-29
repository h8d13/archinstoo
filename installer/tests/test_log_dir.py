# The log directory must not depend on the cwd: `Path.cwd() / 'logs'` used to
# give ./RUN (which cds into installer/) and pytest (run from the repo root)
# a logs/ each. It is derived from __file__ instead, with a rootless fallback
# for the scripts in ROOTLESS_SCRIPTS.

import os
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib import output

if TYPE_CHECKING:
	import pytest


def _pin_layout(monkeypatch: pytest.MonkeyPatch, root: Path, *, euid: int) -> None:
	monkeypatch.setattr(output, '_PKG_ROOT', root)
	monkeypatch.setattr(os, 'geteuid', lambda: euid)


def test_source_checkout_logs_beside_the_package(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	(tmp_path / 'pyproject.toml').touch()
	_pin_layout(monkeypatch, tmp_path, euid=1000)

	assert output._default_log_dir() == tmp_path / 'logs'


def test_installed_as_root_logs_to_var_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	# no pyproject.toml beside the package: site-packages, not a checkout
	_pin_layout(monkeypatch, tmp_path, euid=0)

	assert output._default_log_dir() == Path('/var/log/archinstoo')


def test_installed_rootless_logs_to_xdg_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	_pin_layout(monkeypatch, tmp_path, euid=1000)
	monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))

	assert output._default_log_dir() == tmp_path / 'state' / 'archinstoo'


def test_log_dir_ignores_the_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	(tmp_path / 'pyproject.toml').touch()
	_pin_layout(monkeypatch, tmp_path, euid=1000)

	monkeypatch.chdir(tmp_path)
	from_here = output._default_log_dir()
	monkeypatch.chdir(Path(__file__).parent)

	assert output._default_log_dir() == from_here
