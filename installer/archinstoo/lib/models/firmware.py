from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import NotRequired, Self, TypedDict


class FirmwareType(StrEnum):
	FULL = auto()
	MINIMAL = auto()
	VENDOR = auto()


class FirmwareVendor(StrEnum):
	AMD = 'linux-firmware-amd'  # non-GPU AMD devices, GPUs are AMDGPU/RADEON
	AMDGPU = 'linux-firmware-amdgpu'
	ATHEROS = 'linux-firmware-atheros'
	BROADCOM = 'linux-firmware-broadcom'
	CIRRUS = 'linux-firmware-cirrus'
	INTEL = 'linux-firmware-intel'
	LIQUIDIO = 'linux-firmware-liquidio'
	MARVELL = 'linux-firmware-marvell'
	MEDIATEK = 'linux-firmware-mediatek'
	MELLANOX = 'linux-firmware-mellanox'
	NFP = 'linux-firmware-nfp'
	NVIDIA = 'linux-firmware-nvidia'
	OTHER = 'linux-firmware-other'
	QCOM = 'linux-firmware-qcom'
	QLOGIC = 'linux-firmware-qlogic'
	RADEON = 'linux-firmware-radeon'
	REALTEK = 'linux-firmware-realtek'
	TI = 'linux-firmware-ti'


# linux-firmware's optdeps, test_firmware.py checks the enum against `pacman -Si`
FIRMWARE_OPTDEPS = frozenset(
	{
		FirmwareVendor.LIQUIDIO,
		FirmwareVendor.MARVELL,
		FirmwareVendor.MELLANOX,
		FirmwareVendor.NFP,
		FirmwareVendor.QCOM,
		FirmwareVendor.QLOGIC,
	}
)

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
