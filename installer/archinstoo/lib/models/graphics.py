from enum import Enum


class GfxPackage(Enum):
	# Fedora builds Mesa as two packages: GL plus VA-API in the dri one, every
	# vulkan driver (radv, anv, nvk, lavapipe, venus, the SoC ones) in the other
	MesaDri = 'mesa-dri-drivers'
	MesaVulkan = 'mesa-vulkan-drivers'
	IntelMediaDriver = 'libva-intel-media-driver'
	IntelVplGpuRt = 'intel-vpl-gpu-rt'
	LibVpl = 'libvpl'
	XorgAmdgpu = 'xorg-x11-drv-amdgpu'
	XorgAti = 'xorg-x11-drv-ati'
	XorgNouveau = 'xorg-x11-drv-nouveau'


class GfxDriver(Enum):
	# NVIDIA's own module is RPM Fusion's akmod-nvidia, not in Fedora's repos
	AllOpenSource = 'all-open-source'
	AmdOpenSource = 'amd-open-source'
	IntelOpenSource = 'intel-open-source'
	NvidiaOpenSource = 'nvidia-open-nouveau'
	MesaOpenSource = 'mesa-open-source'
	Custom = 'custom'

	def display_name(self) -> str:
		match self:
			case GfxDriver.AllOpenSource:
				return 'All open-source'
			case GfxDriver.AmdOpenSource:
				return 'AMD / ATI (open-source)'
			case GfxDriver.IntelOpenSource:
				return 'Intel (open-source)'
			case GfxDriver.NvidiaOpenSource:
				return 'Nvidia (open-source nouveau/nvk)'
			case GfxDriver.MesaOpenSource:
				return 'Mesa (VMs, generic GPUs)'
			case GfxDriver.Custom:
				return 'Custom (pick packages)'

	def packages_text(self) -> str:
		if self is GfxDriver.Custom:
			return 'Packages are picked one by one in the next menu (hybrid GPUs, unlisted mixes)\n'

		text = 'Installed packages:\n'
		for p in sorted(p.value for p in self.gfx_packages()):
			text += f'\t- {p}\n'
		return text

	def gfx_packages(self) -> list[GfxPackage]:
		return list(GFX_PACKAGES[self])


# what the custom driver lets a user tick
GFX_CUSTOM_CHOICES: list[GfxPackage] = list(GfxPackage)

# hidden per arch: Intel media and VPL are x86-only builds
_HIDDEN: dict[str, frozenset[GfxPackage]] = {
	'aarch64': frozenset({GfxPackage.IntelMediaDriver, GfxPackage.IntelVplGpuRt}),
}

_MESA = [GfxPackage.MesaDri, GfxPackage.MesaVulkan]
_INTEL = [GfxPackage.IntelMediaDriver, GfxPackage.IntelVplGpuRt, GfxPackage.LibVpl]

GFX_PACKAGES: dict[GfxDriver, list[GfxPackage]] = {
	GfxDriver.AllOpenSource: [*_MESA, GfxPackage.XorgAmdgpu, GfxPackage.XorgAti, GfxPackage.XorgNouveau, *_INTEL],
	GfxDriver.AmdOpenSource: [*_MESA, GfxPackage.XorgAmdgpu, GfxPackage.XorgAti],
	GfxDriver.IntelOpenSource: [*_MESA, *_INTEL],
	GfxDriver.NvidiaOpenSource: [*_MESA, GfxPackage.XorgNouveau],
	GfxDriver.MesaOpenSource: _MESA,
	GfxDriver.Custom: [],
}


def gfx_custom_choices(arch: str) -> list[GfxPackage]:
	hidden = _HIDDEN.get(arch, frozenset())
	return [p for p in GFX_CUSTOM_CHOICES if p not in hidden]


def gfx_drivers(arch: str) -> list[GfxDriver]:
	# a preset shows when none of its packages is hidden on this arch
	hidden = _HIDDEN.get(arch, frozenset())
	return [d for d in GfxDriver if hidden.isdisjoint(GFX_PACKAGES[d])]
