# BOOT reuses its root across runs: once the deps are installed, a rerun must
# not touch dnf (loading repo metadata from a slow mirror took minutes)

import importlib.machinery
import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


def _load_boot() -> ModuleType:
	path = Path(__file__).parents[2] / 'BOOT'
	loader = importlib.machinery.SourceFileLoader('boot', str(path))
	spec = importlib.util.spec_from_loader('boot', loader)
	assert spec is not None
	module = importlib.util.module_from_spec(spec)
	loader.exec_module(module)
	return module


def _fake_bin(bin_dir: Path, name: str, body: str) -> None:
	tool = bin_dir / name
	tool.write_text(f'#!/bin/sh\n{body}\n')
	tool.chmod(0o755)


@pytest.mark.parametrize(('rpm_exit', 'dnf_runs'), [(0, False), (1, True)])
def test_dnf_only_when_deps_missing(tmp_path: Path, rpm_exit: int, dnf_runs: bool) -> None:
	boot = _load_boot()
	calls = tmp_path / 'dnf.args'
	_fake_bin(tmp_path, 'rpm', f'exit {rpm_exit}')
	_fake_bin(tmp_path, 'dnf', f'echo "$@" > {calls}')

	subprocess.run(['/bin/sh', '-c', boot.install_deps_cmd()], env={'PATH': str(tmp_path)}, check=True)

	assert calls.exists() is dnf_runs
	if dnf_runs:
		argv = calls.read_text().split()
		assert '--refresh' not in argv
		assert '--disablerepo=fedora-cisco-openh264' in argv
		assert argv[-len(boot.DEPENDS) :] == list(boot.DEPENDS)
