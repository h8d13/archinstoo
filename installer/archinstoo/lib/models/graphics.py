from enum import Enum


class GfxPackage(Enum):
	Dkms = 'dkms'
	IntelMediaDriver = 'intel-media-driver'
	LibvaIntelDriver = 'libva-intel-driver'
	LibvaNvidiaDriver = 'libva-nvidia-driver'
	Mesa = 'mesa'  # provides libva-mesa-driver since 24.2.7
	NvidiaOpen = 'nvidia-open'
	NvidiaOpenDkms = 'nvidia-open-dkms'
	VplGpuRt = 'vpl-gpu-rt'
	LibVpl = 'libvpl'
	VulkanAsahi = 'vulkan-asahi'
	VulkanBroadcom = 'vulkan-broadcom'
	VulkanDzn = 'vulkan-dzn'
	VulkanFreedreno = 'vulkan-freedreno'
	VulkanGfxstream = 'vulkan-gfxstream'
	VulkanIntel = 'vulkan-intel'
	VulkanMesaLayers = 'vulkan-mesa-layers'
	VulkanPanfrost = 'vulkan-panfrost'
	VulkanPowervr = 'vulkan-powervr'
	VulkanRadeon = 'vulkan-radeon'
	VulkanNouveau = 'vulkan-nouveau'
	VulkanSwrast = 'vulkan-swrast'
	VulkanVirtio = 'vulkan-virtio'
	Xf86VideoAmdgpu = 'xf86-video-amdgpu'
	Xf86VideoAti = 'xf86-video-ati'
	Xf86VideoNouveau = 'xf86-video-nouveau'


class GfxDriver(Enum):
	AllOpenSource = 'all-open-source'
	AmdOpenSource = 'amd-open-source'
	IntelOpenSource = 'intel-open-source'
	NvidiaOpenKernel = 'nvidia-open-kernel'
	NvidiaOpenSource = 'nvidia-open-nouveau'
	MesaOpenSource = 'mesa-open-source'
	VMSoftware = 'vm-software'
	VMVirtio = 'vm-virtio'
	Custom = 'custom'

	def display_name(self) -> str:
		match self:
			case GfxDriver.AllOpenSource:
				return 'All open-source'
			case GfxDriver.AmdOpenSource:
				return 'AMD / ATI (open-source)'
			case GfxDriver.IntelOpenSource:
				return 'Intel (open-source)'
			case GfxDriver.NvidiaOpenKernel:
				return 'Nvidia (open kernel module for newer GPUs, Turing+)'
			case GfxDriver.NvidiaOpenSource:
				return 'Nvidia (open-source nouveau driver)'
			case GfxDriver.MesaOpenSource:
				return 'Mesa (open-source)'
			case GfxDriver.VMSoftware:
				return 'VM (software rendering)'
			case GfxDriver.VMVirtio:
				return 'VM (virtio-gpu)'
			case GfxDriver.Custom:
				return 'Custom (pick packages)'

	def has_dkms_variant(self) -> bool:
		match self:
			case GfxDriver.NvidiaOpenKernel:
				return True
			case _:
				return False

	def packages_text(self, kernels: list[str] | None = None) -> str:
		if self is GfxDriver.Custom:
			return 'Packages are picked one by one in the next menu (hybrid GPUs, unlisted mixes)\n'

		pkg_names = [p.value for p in self.gfx_packages(kernels)]
		text = 'Installed packages' + ':\n'

		for p in sorted(pkg_names):
			text += f'\t- {p}\n'

		return text

	def gfx_packages(self, kernels: list[str] | None = None) -> list[GfxPackage]:
		return dkms_packages(GFX_PACKAGES[self], kernels)


def needs_dkms_build(kernels: list[str] | None) -> bool:
	# anything but plain `linux` has no prebuilt nvidia-open module
	return kernels is not None and any('-' in k for k in kernels)


def dkms_packages(packages: list[GfxPackage], kernels: list[str] | None) -> list[GfxPackage]:
	# nvidia-open is the only out-of-tree driver: a non-standard kernel swaps
	# it for the dkms build and pulls dkms itself. Everything else is in-tree
	if GfxPackage.NvidiaOpen not in packages or not needs_dkms_build(kernels):
		return list(packages)
	swapped: list[GfxPackage] = [GfxPackage.NvidiaOpenDkms if p is GfxPackage.NvidiaOpen else p for p in packages]
	return [*swapped, GfxPackage.Dkms]


# what the custom driver lets a user tick on any arch. dkms and its nvidia
# variant are derived from the kernel list
GFX_CUSTOM_CHOICES: list[GfxPackage] = [p for p in GfxPackage if p not in (GfxPackage.Dkms, GfxPackage.NvidiaOpenDkms)]

# hidden per arch. x86_64 repos carry the SoC and translation-layer vulkan
# drivers, but no x86 GPU uses them; Arch Ports aarch64 builds no Intel media
_HIDDEN: dict[str, frozenset[GfxPackage]] = {
	'x86_64': frozenset(
		{
			GfxPackage.VulkanAsahi,
			GfxPackage.VulkanBroadcom,
			GfxPackage.VulkanDzn,
			GfxPackage.VulkanFreedreno,
			GfxPackage.VulkanGfxstream,
			GfxPackage.VulkanPanfrost,
			GfxPackage.VulkanPowervr,
		}
	),
	'aarch64': frozenset({GfxPackage.IntelMediaDriver, GfxPackage.LibvaIntelDriver, GfxPackage.VplGpuRt}),
}


def gfx_custom_choices(arch: str) -> list[GfxPackage]:
	hidden = _HIDDEN.get(arch, frozenset())
	return [p for p in GFX_CUSTOM_CHOICES if p not in hidden]


def gfx_drivers(arch: str) -> list[GfxDriver]:
	# a preset shows when none of its packages is hidden. On x86_64 the
	# vendor presets cover what plain mesa would
	hidden = _HIDDEN.get(arch, frozenset())
	return [d for d in GfxDriver if hidden.isdisjoint(GFX_PACKAGES[d]) and not (arch == 'x86_64' and d is GfxDriver.MesaOpenSource)]


# the static half of every driver, before the DKMS swap
GFX_PACKAGES: dict[GfxDriver, list[GfxPackage]] = {
	GfxDriver.AllOpenSource: [
		GfxPackage.Mesa,
		GfxPackage.Xf86VideoAmdgpu,
		GfxPackage.Xf86VideoAti,
		GfxPackage.Xf86VideoNouveau,
		GfxPackage.LibvaIntelDriver,
		GfxPackage.IntelMediaDriver,
		GfxPackage.VplGpuRt,
		GfxPackage.LibVpl,
		GfxPackage.VulkanRadeon,
		GfxPackage.VulkanIntel,
		GfxPackage.VulkanNouveau,
	],
	GfxDriver.AmdOpenSource: [
		GfxPackage.Mesa,
		GfxPackage.Xf86VideoAmdgpu,
		GfxPackage.Xf86VideoAti,
		GfxPackage.VulkanRadeon,
	],
	GfxDriver.IntelOpenSource: [
		GfxPackage.Mesa,
		GfxPackage.LibvaIntelDriver,
		GfxPackage.IntelMediaDriver,
		GfxPackage.VplGpuRt,
		GfxPackage.LibVpl,
		GfxPackage.VulkanIntel,
	],
	GfxDriver.NvidiaOpenKernel: [
		GfxPackage.NvidiaOpen,
		GfxPackage.LibvaNvidiaDriver,
	],
	GfxDriver.NvidiaOpenSource: [
		GfxPackage.Mesa,
		GfxPackage.Xf86VideoNouveau,
		GfxPackage.VulkanNouveau,
	],
	GfxDriver.MesaOpenSource: [
		GfxPackage.Mesa,
	],
	GfxDriver.VMSoftware: [
		GfxPackage.Mesa,
		GfxPackage.VulkanSwrast,
	],
	GfxDriver.Custom: [],
	GfxDriver.VMVirtio: [
		GfxPackage.Mesa,
		GfxPackage.VulkanVirtio,
	],
}
