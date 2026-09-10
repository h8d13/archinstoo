# Guest agents by hypervisor: kvm gets qemu-guest-agent, bare metal gets nothing.
# https://github.com/archlinux/archinstall/issues/1476

from types import SimpleNamespace

import pytest

from archinstoo.lib import installer as mod
from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.installer import Installer


def _run(monkeypatch: pytest.MonkeyPatch, name: str) -> tuple[list[list[str]], list[list[str]]]:
	strapped: list[list[str]] = []
	enabled: list[list[str]] = []
	monkeypatch.setattr(SysInfo, 'hypervisor', staticmethod(lambda: name))
	inst = Installer.__new__(Installer)
	inst.pacman = SimpleNamespace(strap=lambda pkgs: strapped.append(list(pkgs)))  # type: ignore[assignment]
	monkeypatch.setattr(inst, 'enable_service', lambda svcs: enabled.append(list(svcs)), raising=False)
	inst.setup_vm_guest()
	return strapped, enabled


def test_kvm_gets_qemu_guest_agent(monkeypatch: pytest.MonkeyPatch) -> None:
	# static unit, udev-activated: nothing to enable
	assert _run(monkeypatch, 'kvm') == ([['qemu-guest-agent', 'spice-vdagent']], [])


def test_hyperv_gets_all_three_daemons(monkeypatch: pytest.MonkeyPatch) -> None:
	_, enabled = _run(monkeypatch, 'microsoft')
	assert enabled == [['hv_fcopy_daemon', 'hv_kvp_daemon', 'hv_vss_daemon']]


@pytest.mark.parametrize('name', ['', 'xen', 'parallels'])
def test_unknown_or_bare_metal_does_nothing(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
	assert _run(monkeypatch, name) == ([], [])


def test_every_map_entry_has_packages() -> None:
	for name, (packages, _services) in mod.__vm_guest__.items():
		assert packages, name


def test_config_toggle_round_trip() -> None:
	from archinstoo.lib.args import ArchConfig

	assert ArchConfig().vm_guest is True
	assert ArchConfig.from_config({'vm_guest': False}).vm_guest is False
	assert ArchConfig.from_config({}).vm_guest is True
	assert ArchConfig(vm_guest=False).safe_json()['vm_guest'] is False
