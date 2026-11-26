from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Self

# Base packages installed by default (firmware added based on FirmwareConfiguration)
# mkinitcpio is listed explicitly so pacstrap installs it deterministically. Otherwise
# pacman picks the first initramfs provider from the host's pacman.conf, which on
# non-Arch hosts (EndeavourOS prefers dracut, etc.) breaks the initramfs build and the
# UKI presets, both of which assume mkinitcpio is present in the chroot.
BASE_PACKAGES = ['base', 'mkinitcpio']
# Arch Ports (aarch64) ships its keyring from forge, not as a pacman dependency
ARCHPORTS_PACKAGES = ['archports-keyring']

# Package sets minimal_installation() and the steps after it add conditionally.
# Named rather than inlined so schema_gen can read the same list the installer
# straps, instead of a transcription of it.
LVM = 'lvm2'  # package and mkinitcpio hook share the name
LVM_PACKAGES = [LVM]
# sd-encrypt only bundles the fido2 dlopen libs if this is present when the
# initramfs is built
FIDO2_PACKAGES = ['libfido2']
# the array has to be assembled before the root is reachable, so this goes
# into base rather than the post-install package list
RAID_PACKAGES = ['mdadm']
# fonts that are in the ISO but won't be on target unless requested before base,
# otherwise mkinitcpio will be screaming at you
TER_FONT_PACKAGES = ['terminus-font']

# Additional packages that are installed if the user is running the Live ISO with
# accessibility tools enabled
ACCESSIBILITY_PACKAGES = ['brltty', 'espeakup', 'alsa-utils']


class Repository(Enum):
	Core = 'core'
	Extra = 'extra'
	# Arch Ports (aarch64): board kernels, firmware and archports-keyring;
	# always enabled in the port's pacman.conf, listed so it is not custom
	Forge = 'forge'
	Multilib = 'multilib'
	Testing = 'testing'
	MultilibTesting = 'multilib-testing'
	CoreTesting = 'core-testing'
	ExtraTesting = 'extra-testing'


# slotted: list_available_packages() holds one per sync-db package (~15k)
@dataclass(slots=True)
class AvailablePackage:
	name: str
	architecture: str
	build_date: str
	conflicts_with: str
	depends_on: str
	description: str
	download_size: str
	groups: str
	installed_size: str
	licenses: str
	optional_deps: str
	packager: str
	provides: str
	replaces: str
	repository: str
	url: str
	validated_by: str
	version: str

	def info(self) -> str:
		values = asdict(self)
		width = max(len(key) for key in values)
		output = ''
		for key, value in values.items():
			label = key.replace('_', ' ').capitalize().ljust(width)
			output += f'{label} : {value}\n'

		return output


@dataclass
class PackageGroup:
	name: str
	packages: list[str] = field(default_factory=list)

	@classmethod
	def from_available_packages(
		cls,
		packages: dict[str, AvailablePackage],
	) -> dict[str, Self]:
		pkg_groups: dict[str, Self] = {}

		for pkg in packages.values():
			if 'None' in pkg.groups:
				continue

			groups = pkg.groups.split(' ')

			for group in groups:
				# same group names have multiple spaces in between
				if len(group) == 0:
					continue

				pkg_groups.setdefault(group, cls(group))
				pkg_groups[group].packages.append(pkg.name)

		return pkg_groups

	def info(self) -> str:
		output = 'Package group:\n  - '
		output += '\n  - '.join(self.packages)
		return output
