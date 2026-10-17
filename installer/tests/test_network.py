# Every network type ends up on systemd-resolved; the stub symlink and the
# enabled service are what the DNS choice builds on.

from pathlib import Path

import pytest

from archinstoo.lib.installer import Installer
from archinstoo.lib.models.network import DnsConfiguration, DnsProvider, NetworkConfiguration, NicType
from archinstoo.lib.network import network_handler
from archinstoo.lib.network.network_handler import NetworkHandler
from archinstoo.lib.utils.host import Host

STUB = '/run/systemd/resolve/stub-resolv.conf'


def _session(target: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Installer, list[str]]:
	installation = Installer.__new__(Installer)
	installation.target = target
	enabled: list[str] = []
	monkeypatch.setattr(installation, 'enable_service', lambda s: enabled.extend([s] if isinstance(s, str) else s), raising=False)
	monkeypatch.setattr(installation, 'disable_service', lambda s: None, raising=False)
	monkeypatch.setattr(installation, 'add_additional_packages', lambda pkgs: None, raising=False)
	monkeypatch.setattr(Host, 'running_from_foreign', lambda: False)
	return installation, enabled


@pytest.mark.parametrize('nic_type', [NicType.NM, NicType.NM_IWD, NicType.IWD, NicType.MANUAL])
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


# -- DNS ---------------------------------------------------------------------

QUAD9_TLS = """[Resolve]
DNS=9.9.9.9#dns.quad9.net 149.112.112.112#dns.quad9.net 2620:fe::fe#dns.quad9.net 2620:fe::9#dns.quad9.net
DNSOverTLS=yes
Domains=~.
"""


def test_dns_over_tls_drop_in() -> None:
	assert DnsConfiguration(DnsProvider.QUAD9).as_resolved_config() == QUAD9_TLS


def test_dns_plain_drop_in_names_no_tls() -> None:
	conf = DnsConfiguration(DnsProvider.CLOUDFLARE, over_tls=False).as_resolved_config()
	assert 'DNSOverTLS' not in conf
	assert '#' not in conf
	assert 'Domains=~.' in conf


@pytest.mark.parametrize('nic_type', [NicType.NM, NicType.IWD])
def test_dns_choice_lands_in_resolved_conf_d(nic_type: NicType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	(tmp_path / 'etc').mkdir()
	installation, _ = _session(tmp_path, monkeypatch)

	NetworkHandler().install_network_config(NetworkConfiguration(nic_type, dns=DnsConfiguration(DnsProvider.QUAD9)), installation)

	assert (tmp_path / 'etc/systemd/resolved.conf.d/dns.conf').read_text() == QUAD9_TLS


def test_no_dns_choice_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	(tmp_path / 'etc').mkdir()
	installation, _ = _session(tmp_path, monkeypatch)

	NetworkHandler().install_network_config(NetworkConfiguration(NicType.NM), installation)

	assert not (tmp_path / 'etc/systemd/resolved.conf.d').exists()


def test_dns_round_trips_through_json() -> None:
	config = NetworkConfiguration(NicType.NM_IWD, dns=DnsConfiguration(DnsProvider.GOOGLE, over_tls=False))
	assert NetworkConfiguration.parse_arg(config.json()) == config

	# absent stays absent, and a manual type with no interfaces is still nothing
	assert NetworkConfiguration.parse_arg({'type': 'nm'}) == NetworkConfiguration(NicType.NM)
	assert NetworkConfiguration.parse_arg({'type': 'manual'}) is None


# A foreign host (alpine, debian) keeps nothing the target can read: busybox
# udhcpc holds its lease in memory and writes no config, so 'copy from ISO'
# copied nothing and the install ended with no DHCP client and no .network.
def _iso_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
	empty = tmp_path / 'empty-host'
	empty.mkdir()
	monkeypatch.setattr(network_handler, 'ISO_IWD_DIR', str(empty))
	monkeypatch.setattr(network_handler, 'ISO_NETWORK_DIR', str(empty))


def test_iso_copy_falls_back_to_wired_dhcp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	(tmp_path / 'etc').mkdir()
	installation, enabled = _session(tmp_path, monkeypatch)
	_iso_sources(monkeypatch, tmp_path)

	NetworkHandler().install_network_config(NetworkConfiguration(NicType.ISO), installation)

	wired = (tmp_path / 'etc/systemd/network/20-wired.network').read_text()
	assert 'DHCP=yes' in wired
	assert 'Type=ether' in wired
	assert 'systemd-networkd' in enabled
