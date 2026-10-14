from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import NotRequired, Self, TypedDict


class FirmwareType(StrEnum):
	FULL = auto()
	MINIMAL = auto()
	VENDOR = auto()


class FirmwareVendor(StrEnum):
	# Fedora's linux-firmware splits
	AMDGPU = 'amd-gpu-firmware'
	ATHEROS = 'atheros-firmware'
	BROADCOM = 'brcmfmac-firmware'
	CIRRUS = 'cirrus-audio-firmware'
	INTEL_AUDIO = 'intel-audio-firmware'
	INTEL_GPU = 'intel-gpu-firmware'
	INTEL_NPU = 'intel-npu-firmware'
	INTEL_VSC = 'intel-vsc-firmware'
	IWLBLUETOOTH = 'iwlbluetooth-firmware'
	IWLEGACY = 'iwlegacy-firmware'
	IWLWIFI_DVM = 'iwlwifi-dvm-firmware'
	IWLWIFI_MLD = 'iwlwifi-mld-firmware'
	IWLWIFI_MVM = 'iwlwifi-mvm-firmware'
	LIBERTAS = 'libertas-firmware'
	LIQUIDIO = 'liquidio-firmware'
	MEDIATEK = 'mediatek-firmware'
	MLXSW = 'mlxsw_spectrum-firmware'
	MRVLPRESTERA = 'mrvlprestera-firmware'
	MT7XXX = 'mt7xxx-firmware'
	NETRONOME = 'netronome-firmware'
	NVIDIA = 'nvidia-gpu-firmware'
	NXPWIRELESS = 'nxpwireless-firmware'
	QCOM = 'qcom-firmware'
	QCOM_WWAN = 'qcom-wwan-firmware'
	QED = 'qed-firmware'
	REALTEK = 'realtek-firmware'
	TIWILINK = 'tiwilink-firmware'


# what linux-firmware only Recommends, so a FULL install gets it anyway; the
# rest stay opt-in (test_firmware.py checks the set against the repos)
_RECOMMENDED = frozenset(
	{
		FirmwareVendor.AMDGPU,
		FirmwareVendor.ATHEROS,
		FirmwareVendor.BROADCOM,
		FirmwareVendor.CIRRUS,
		FirmwareVendor.INTEL_AUDIO,
		FirmwareVendor.INTEL_GPU,
		FirmwareVendor.MT7XXX,
		FirmwareVendor.NVIDIA,
		FirmwareVendor.NXPWIRELESS,
		FirmwareVendor.QCOM_WWAN,
		FirmwareVendor.REALTEK,
		FirmwareVendor.TIWILINK,
	}
)
FIRMWARE_OPTDEPS = frozenset(FirmwareVendor) - _RECOMMENDED

FULL_FIRMWARE = ['linux-firmware']


class FirmwareConfigSerialization(TypedDict):
	firmware_type: str
	vendors: NotRequired[list[str]]


@dataclass
class FirmwareConfiguration:
	firmware_type: FirmwareType = FirmwareType.FULL
	vendors: list[FirmwareVendor] = field(default_factory=list)

	@classmethod
	def default(cls) -> Self:
		# Guests boot on virtio/emulated devices that ship no blobs. Bare metal keeps
		# FULL: a missed blob can cost the only NIC, with no network left to fix it.
		from archinstoo.lib.hardware import SysInfo

		if SysInfo.is_vm():
			return cls(firmware_type=FirmwareType.MINIMAL)
		return cls()

	def packages(self) -> list[str]:
		# FULL's vendors are the picked optdeps, VENDOR's the picked splits
		match self.firmware_type:
			case FirmwareType.FULL:
				return [*FULL_FIRMWARE, *self.vendors]
			case FirmwareType.MINIMAL:
				return []
			case FirmwareType.VENDOR:
				return list(self.vendors)

	def json(self) -> FirmwareConfigSerialization:
		out: FirmwareConfigSerialization = {'firmware_type': self.firmware_type.value}
		if self.vendors:
			out['vendors'] = [v.value for v in self.vendors]
		return out

	@classmethod
	def parse_arg(cls, arg: FirmwareConfigSerialization) -> Self:
		firmware_type = FirmwareType(arg['firmware_type'])
		vendors = [FirmwareVendor(v) for v in arg.get('vendors', [])]
		return cls(firmware_type=firmware_type, vendors=vendors)
