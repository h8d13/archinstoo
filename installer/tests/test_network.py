# Every network type ends up on systemd-resolved; the stub symlink and the
# enabled service are what the DNS choice builds on.

from pathlib import Path

import pytest

from archinstoo.lib.installer import Installer
from archinstoo.lib.models.network import DnsConfiguration, DnsProvider, MacAddressPolicy, NetworkConfiguration, NicType
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


@pytest.mark.parametrize('nic_type', [NicType.IWD, NicType.MANUAL])
def test_random_mac_link_keeps_predictable_names(nic_type: NicType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# the .link matches every interface and sorts before 99-default.link, so
	# it replaces it: without the naming policies the NIC boots as eth0 and a
	# manual Name=enp0s2 match never applies (seen on the VM, 2026-09-07)
	(tmp_path / 'etc').mkdir()
	installation, _ = _session(tmp_path, monkeypatch)

	config = NetworkConfiguration(nic_type, mac_address=MacAddressPolicy.RANDOM)
	NetworkHandler().install_network_config(config, installation)

	link = (tmp_path / 'etc/systemd/network/00-mac-address.link').read_text()
	assert 'NamePolicy=keep kernel database onboard slot path' in link
	assert 'AlternativeNamesPolicy=database onboard slot path mac' in link
	assert 'MACAddressPolicy=random' in link


@pytest.mark.parametrize(('mac', 'mode'), [(MacAddressPolicy.STABLE, 'network'), (MacAddressPolicy.RANDOM, 'once')])
def test_nm_iwd_mac_lands_in_iwd_conf(mac: MacAddressPolicy, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# NM's iwd backend ignores cloned-mac-address for wireless, so the choice
	# has to reach /etc/iwd/main.conf as well as the NM drop-in
	(tmp_path / 'etc').mkdir()
	installation, _ = _session(tmp_path, monkeypatch)

	NetworkHandler().install_network_config(NetworkConfiguration(NicType.NM_IWD, mac_address=mac), installation)

	assert (tmp_path / 'etc/iwd/main.conf').read_text() == f'[General]\nAddressRandomization={mode}\n'
	assert f'wifi.cloned-mac-address={mac.value}' in (tmp_path / 'etc/NetworkManager/conf.d/mac_address.conf').read_text()
	assert not (tmp_path / 'etc/systemd/network/00-mac-address.link').exists()


def test_stable_mac_without_nm_writes_no_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	(tmp_path / 'etc').mkdir()
	installation, _ = _session(tmp_path, monkeypatch)

	NetworkHandler().install_network_config(NetworkConfiguration(NicType.MANUAL, mac_address=MacAddressPolicy.STABLE), installation)

	assert not (tmp_path / 'etc/systemd/network/00-mac-address.link').exists()
