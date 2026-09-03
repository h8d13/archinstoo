from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import NotRequired, Self, TypedDict


class FirmwareType(StrEnum):
	FULL = auto()
	MINIMAL = auto()
	VENDOR = auto()


class FirmwareVendor(StrEnum):
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


# linux-firmware's OPTIONAL deps only. pacman never pulls them in, so their
# files are absent and detect_splits() can find no owner to name: an ID is the
# last source left. Its hard deps arrive with FULL anyway and stay out of here.
# Vendor-wide, so a ConnectX over-installs a few MB. IDs from pci.ids.
# QCOM has none: SoC blobs sit on the platform bus, no PCI ID to match.
_OPTDEP_PCI: dict[str, FirmwareVendor] = {
	'0x1077': FirmwareVendor.QLOGIC,
	'0x11ab': FirmwareVendor.MARVELL,
	'0x15b3': FirmwareVendor.MELLANOX,
	'0x177d': FirmwareVendor.LIQUIDIO,  # pci.ids says Cavium
	'0x19ee': FirmwareVendor.NFP,  # pci.ids says Netronome
	'0x1b4b': FirmwareVendor.MARVELL,
}

# BT radios and wifi dongles hang off USB even when the wifi itself is PCIe
_OPTDEP_USB: dict[str, FirmwareVendor] = {
	'1286': FirmwareVendor.MARVELL,
}

# The catch-all names no vendor, so no owner lookup can ever land on it
_SPLIT_BASELINE = (FirmwareVendor.OTHER,)


def detect_optdeps() -> list[FirmwareVendor]:
	from archinstoo.lib.hardware import SysInfo

	pci, usb = SysInfo.bus_vendor_ids()
	found = {v for i, v in _OPTDEP_PCI.items() if i in pci}
	found |= {v for i, v in _OPTDEP_USB.items() if i in usb}

	return sorted(found)


def detect_splits() -> list[FirmwareVendor]:
	from archinstoo.lib.hardware import SysInfo

	# owners that are not splits (sof-firmware, the nvidia driver tree) have no
	# member to resolve to and drop, as does a split Arch adds before we do
	members = {v.value: v for v in FirmwareVendor}
	found = {members[pkg] for pkg in SysInfo.firmware_owners() if pkg in members}

	return sorted(found | set(_SPLIT_BASELINE))


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
		match self.firmware_type:
			case FirmwareType.FULL:
				# the metapackage stops at its hard deps, all opts pkgs are dropped
				# we re-register them here based on PCI ID detection
				return ['linux-firmware', *(v.value for v in detect_optdeps())]
			case FirmwareType.MINIMAL:
				return []
			case FirmwareType.VENDOR:
				return [v.value for v in self.vendors]

	def json(self) -> FirmwareConfigSerialization:
		out: FirmwareConfigSerialization = {'firmware_type': self.firmware_type.value}
		if self.firmware_type == FirmwareType.VENDOR:
			out['vendors'] = [v.value for v in self.vendors]
		return out

	@classmethod
	def parse_arg(cls, arg: FirmwareConfigSerialization) -> Self:
		firmware_type = FirmwareType(arg['firmware_type'])
		vendors = [FirmwareVendor(v) for v in arg.get('vendors', [])]
		return cls(firmware_type=firmware_type, vendors=vendors)
