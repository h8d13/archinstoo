import os
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from archinstoo.lib import hardware
from archinstoo.lib.models.firmware import FIRMWARE_OPTDEPS, FirmwareConfiguration, FirmwareType, FirmwareVendor

if TYPE_CHECKING:
	from pathlib import Path


def _repoquery(*args: str) -> set[str] | None:
	proc = subprocess.run(  # noqa: S603 - fixed argv
		['dnf', 'repoquery', '-q', *args],  # noqa: S607 - dnf from $PATH
		capture_output=True,
		text=True,
		check=False,
		env={**os.environ, 'LC_ALL': 'C'},
	)
	if proc.returncode != 0:
		return None
	return {line.split()[0] for line in proc.stdout.splitlines() if line.strip()}


def test_enum_matches_fedora_metadata() -> None:
	# the enum is hand kept, a split Fedora adds or retires fails here
	if not shutil.which('dnf'):
		pytest.skip('no dnf')
	recommends = _repoquery('--recommends', 'linux-firmware')
	splits = _repoquery('--qf', '%{name}\\n', *(v.value for v in FirmwareVendor))
	if recommends is None or splits is None:
		pytest.skip('no repo metadata')

	assert {v.value for v in FirmwareVendor} == splits
	assert {v.value for v in FirmwareVendor if v not in FIRMWARE_OPTDEPS} == recommends & splits


# -- hardware probes -------------------------------------------------------------


@pytest.mark.parametrize(
	('modules', 'sof', 'alsa'),
	[
		(['snd_hda_intel'], False, False),
		(['snd_sof', 'snd_sof_pci_intel_tgl'], True, False),
		(['snd_hda_intel', 'snd_hda_codec_ca0132'], False, True),
		(['snd_vx_lib', 'snd_pcm'], False, True),
	],
)
def test_sound_firmware_from_loaded_modules(
	monkeypatch: pytest.MonkeyPatch,
	tmp_path: Path,
	modules: list[str],
	sof: bool,
	alsa: bool,
) -> None:
	# /proc/modules: name size refcount deps state address
	proc_modules = tmp_path / 'modules'
	proc_modules.write_text(''.join(f'{m} 16384 0 - Live 0x0000000000000000\n' for m in modules))
	monkeypatch.setattr(hardware, '_PROC_MODULES', proc_modules)
	monkeypatch.setattr(hardware, '_sys_info', hardware._SysInfo())

	assert (hardware.SysInfo.requires_sof_fw(), hardware.SysInfo.requires_alsa_fw()) == (sof, alsa)


def test_is_vm_forks_once(monkeypatch: pytest.MonkeyPatch) -> None:
	# gates microcode and the firmware default
	calls: list[str] = []

	def fake_syscommand(cmd: str) -> list[bytes]:
		calls.append(cmd)
		return [b'none']

	monkeypatch.setattr(hardware, 'SysCommand', fake_syscommand)
	info = hardware._SysInfo()

	assert (info.is_vm, info.is_vm, info.is_vm) == (False, False, False)
	assert calls == ['systemd-detect-virt']


# -- configuration ---------------------------------------------------------------


@pytest.mark.parametrize(
	('is_vm', 'expected'),
	[
		(True, FirmwareType.MINIMAL),
		(False, FirmwareType.FULL),
	],
)
def test_firmware_default_per_host(monkeypatch: pytest.MonkeyPatch, is_vm: bool, expected: FirmwareType) -> None:
	monkeypatch.setattr(hardware.SysInfo, 'is_vm', staticmethod(lambda: is_vm))

	assert FirmwareConfiguration.default().firmware_type is expected


@pytest.mark.parametrize(
	('config', 'expected'),
	[
		(FirmwareConfiguration(), ['linux-firmware']),
		(
			FirmwareConfiguration(vendors=[FirmwareVendor.QCOM]),
			['linux-firmware', 'qcom-firmware'],
		),
		# MINIMAL is an explicit opt-out, a stale pick does not leak through
		(FirmwareConfiguration(firmware_type=FirmwareType.MINIMAL, vendors=[FirmwareVendor.QCOM]), []),
		(
			FirmwareConfiguration(firmware_type=FirmwareType.VENDOR, vendors=[FirmwareVendor.IWLWIFI_MVM]),
			['iwlwifi-mvm-firmware'],
		),
	],
)
def test_firmware_packages(config: FirmwareConfiguration, expected: list[str]) -> None:
	assert config.packages() == expected


@pytest.mark.parametrize(
	'config',
	[
		FirmwareConfiguration(),
		FirmwareConfiguration(vendors=[FirmwareVendor.QCOM]),
		FirmwareConfiguration(firmware_type=FirmwareType.VENDOR, vendors=[FirmwareVendor.IWLWIFI_MVM, FirmwareVendor.REALTEK]),
	],
)
def test_config_round_trip(config: FirmwareConfiguration) -> None:
	assert FirmwareConfiguration.parse_arg(config.json()) == config
