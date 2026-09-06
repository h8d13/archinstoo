# Every network type ends up on systemd-resolved: the three networkd paths
# always did, and NetworkManager switches itself to dns=systemd-resolved when
# /etc/resolv.conf is the resolved stub. That symlink and the enabled service
# are what the DNS options build on.

from pathlib import Path

import pytest

from archinstoo.lib.installer import Installer
from archinstoo.lib.models.network import NetworkConfiguration, NicType
from archinstoo.lib.network.network_handler import NetworkHandler
from archinstoo.lib.utils.env import Os

STUB = '/run/systemd/resolve/stub-resolv.conf'


def _session(target: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Installer, list[str]]:
	installation = Installer.__new__(Installer)
	installation.target = target
	enabled: list[str] = []
	monkeypatch.setattr(installation, 'enable_service', lambda s: enabled.extend([s] if isinstance(s, str) else s), raising=False)
	monkeypatch.setattr(installation, 'disable_service', lambda s: None, raising=False)
	monkeypatch.setattr(installation, 'add_additional_packages', lambda pkgs: None, raising=False)
	monkeypatch.setattr(Os, 'running_from_foreign', lambda: False)
	return installation, enabled


@pytest.mark.parametrize('nic_type', [NicType.NM, NicType.NM_IWD, NicType.IWD])
def test_network_types_resolve_through_resolved(nic_type: NicType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	(tmp_path / 'etc').mkdir()
	installation, enabled = _session(tmp_path, monkeypatch)

	NetworkHandler().install_network_config(NetworkConfiguration(nic_type), installation)

	assert 'systemd-resolved' in enabled
	assert (tmp_path / 'etc/resolv.conf').readlink() == Path(STUB)


def test_nm_iwd_keeps_its_backend_drop_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	(tmp_path / 'etc').mkdir()
	installation, _ = _session(tmp_path, monkeypatch)

	NetworkHandler().install_network_config(NetworkConfiguration(NicType.NM_IWD), installation)

	assert (tmp_path / 'etc/NetworkManager/conf.d/wifi_backend.conf').read_text() == '[device]\nwifi.backend=iwd\n'
