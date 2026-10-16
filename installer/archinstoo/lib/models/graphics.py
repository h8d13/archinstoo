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
	AllOpenSource = 'all-open-source'
	AmdOpenSource = 'amd-open-source'
	IntelOpenSource = 'intel-open-source'
	NvidiaOpenSource = 'nvidia-open-nouveau'
	NvidiaProprietary = 'nvidia-proprietary'
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
			case GfxDriver.NvidiaProprietary:
				return 'Nvidia (proprietary, RPM Fusion)'
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
		if self is GfxDriver.NvidiaProprietary:
			text += 'Then from RPM Fusion (free + nonfree enabled):\n'
			text += ''.join(f'\t- {p}\n' for p in NVIDIA_PROPRIETARY)
			text += 'Turing+ (GTX 16xx, RTX 20xx and newer). Secure Boot off.\n'
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
	GfxDriver.NvidiaProprietary: _MESA,
	GfxDriver.MesaOpenSource: _MESA,
	GfxDriver.Custom: [],
}

# NVIDIA's own module is not in Fedora's repos: RPM Fusion's howto steps,
# installed in the target after Fedora's own packages
# https://rpmfusion.org/Howto/NVIDIA#Current_GeForce.2FQuadro.2FTesla
NVIDIA_PROPRIETARY = ['akmod-nvidia', 'xorg-x11-drv-nvidia-cuda']


def rpmfusion_release_urls(release: str) -> list[str]:
	# https://rpmfusion.org/Configuration
	return [f'https://mirrors.rpmfusion.org/{repo}/fedora/rpmfusion-{repo}-release-{release}.noarch.rpm' for repo in ('free', 'nonfree')]


def gfx_custom_choices(arch: str) -> list[GfxPackage]:
	hidden = _HIDDEN.get(arch, frozenset())
	return [p for p in GFX_CUSTOM_CHOICES if p not in hidden]


def gfx_drivers(arch: str) -> list[GfxDriver]:
	# a preset shows when none of its packages is hidden on this arch
	hidden = _HIDDEN.get(arch, frozenset())
	return [d for d in GfxDriver if hidden.isdisjoint(GFX_PACKAGES[d])]
