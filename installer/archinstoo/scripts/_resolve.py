# Package-set resolution for the count script.
#
# collect() turns a saved config into its explicit package set; resolve_deps()
# expands pacman groups, then the full dependency tree via pactree
# (pacman-contrib). Kept free of a module-level entrypoint so count and the
# tests can import it without side effects.

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from archinstoo.lib.command import SysCommand
from archinstoo.lib.exceptions import RequirementError
from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.host_services import accessibility_tools_in_use
from archinstoo.lib.models.authentication import PrivilegeEscalation
from archinstoo.lib.models.bootloader import Bootloader
from archinstoo.lib.models.device import (
	FilesystemType,
	ModificationStatus,
	SubvolumeModification,
)
from archinstoo.lib.models.firmware import FirmwareConfiguration, FirmwareType
from archinstoo.lib.models.graphics import GfxDriver, GfxPackage, needs_dkms_build
from archinstoo.lib.models.kernel import DEFAULT_KERNEL
from archinstoo.lib.models.network import NicType
from archinstoo.lib.models.profile import DisplayServer
from archinstoo.lib.network.network_handler import ISO_IWD_DIR
from archinstoo.lib.pm.groups import expand
from archinstoo.lib.profile.base import Profile
from archinstoo.lib.schema import SCHEMA
from archinstoo.lib.serialize import strip_none
from archinstoo.lib.utils.paths import locate_binary

if TYPE_CHECKING:
	from archinstoo.lib.args import ArchConfigSerialization
	from archinstoo.lib.models.applications import ApplicationSerialization
	from archinstoo.lib.models.device import (
		_DiskLayoutConfigurationSerialization,
		_LvmVolumeSerialization,
		_PartitionModificationSerialization,
	)
	from archinstoo.lib.models.profile import ProfileSerialization
	from archinstoo.lib.models.users import UserSerialization
	from archinstoo.lib.schema_gen import Section


def _flat(key: str) -> list[str]:
	# sections that are one list rather than a map of options hold it under
	# `packages` (see lib/schema_gen.py for why every section is a table)
	packages: list[str] = SCHEMA[key]['packages']
	return packages


def _requirements(*binaries: str) -> bool:
	try:
		for name in binaries:
			locate_binary(name)
		return True
	except RequirementError:
		return False


def _firmware_packages(config: ArchConfigSerialization) -> set[str]:
	# mirrors FirmwareConfiguration.packages(): the schema holds what is
	# static, the picked vendors come from the config. An unset section is
	# ArchConfig's default, which depends on the host being a VM
	firmware_type = FirmwareConfiguration.default(
		SysInfo.is_vm()
	).firmware_type.value
	vendors: list[str] = []
	if firmware_cfg := config.get('firmware'):
		firmware_type = firmware_cfg.get('firmware_type', firmware_type)
		vendors = firmware_cfg.get('vendors') or []
	pkgs = set(SCHEMA['firmware'].get(firmware_type, []))
	if firmware_type != FirmwareType.MINIMAL.value:
		pkgs.update(vendors)

	return pkgs


def _iso_has_psks() -> bool:
	# mirrors copy_iso_network_config(): the target only needs iwd when there
	# are ISO PSKs to carry over
	return bool(list(Path(ISO_IWD_DIR).glob('*.psk')))


def _host_packages() -> set[str]:
	# what the installer reads off the running system rather than the config;
	# count runs on that same host, so the detection carries over
	pkgs: set[str] = set()

	if accessibility_tools_in_use():
		pkgs.update(_flat('accessibility'))

	if not SysInfo.is_vm() and (vendor := SysInfo.cpu_vendor()):
		pkgs.update(SCHEMA['microcode'].get(vendor.value, []))

	if SysInfo.is_aarch64():
		pkgs.update(_flat('archports'))

	return pkgs


def _status(
	vol: _PartitionModificationSerialization | _LvmVolumeSerialization,
) -> str | None:
	# .get() takes any key and reads one the type lacks as object: the return
	# type is what holds this read to the two serializations
	return vol.get('status')


def _filesystem_packages(disk: _DiskLayoutConfigurationSerialization) -> set[str]:
	# minimal_installation() prepares LVM volumes or partitions, never both, and
	# lvm_config sits next to device_modifications rather than inside them
	fs_tools = SCHEMA['filesystem_tools']
	fs_types: set[str] = set()

	if lvm_config := disk.get('lvm_config'):
		for group in lvm_config.get('vol_groups') or []:
			fs_types.update(
				vol.get('fs_type', '')
				for vol in group.get('volumes') or []
			)
	else:
		for dev in disk.get('device_modifications') or []:
			# a partition on its way out gets no filesystem prepared
			fs_types.update(
				part.get('fs_type') or ''
				for part in dev.get('partitions') or []
				if _status(part) != ModificationStatus.DELETE.value
			)

	pkgs = {p for fs in fs_types if fs in fs_tools for p in fs_tools[fs]}

	if lvm_config:
		pkgs.update(_flat('lvm'))

	return pkgs


def _has_default_btrfs_vols(disk: _DiskLayoutConfigurationSerialization) -> bool:
	# mirrors DiskLayoutConfiguration.has_default_btrfs_vols(): a btrfs
	# partition or LVM volume being set up, with @ mounted on /
	vols: list[_PartitionModificationSerialization | _LvmVolumeSerialization]
	vols = [
		part
		for dev in disk.get('device_modifications') or []
		for part in dev.get('partitions') or []
	]
	if lvm_config := disk.get('lvm_config'):
		for group in lvm_config.get('vol_groups') or []:
			vols += group.get('volumes') or []

	return any(
		_status(vol)
		in {ModificationStatus.CREATE.value, ModificationStatus.MODIFY.value}
		and vol.get('fs_type') == FilesystemType.BTRFS.value
		and any(
			subvol.is_default_root()
			for subvol in SubvolumeModification.parse_args(
				vol.get('btrfs') or []
			)
		)
		for vol in vols
	)


def _profile_packages(name: str, settings: dict[str, Any]) -> set[str]:
	prof_pkgs = set(SCHEMA['profiles'][name])

	# <name>_compositor swaps the default (niri) compositor set. unset, the
	# profile keeps that default
	picked = settings.get(f'{name}_compositor')
	if picked and (comp_sets := SCHEMA['compositors'].get(name)):
		prof_pkgs.difference_update(comp_sets['niri'])
		prof_pkgs.update(comp_sets[picked])

	return prof_pkgs


def _top_profiles(
	entries: list[ProfileSerialization],
) -> tuple[list[Profile], list[Profile]]:
	# every entry as the installer reads it: one whose main names no profile
	# is dropped, a selection loses unknown names and each shell after the
	# first, and a 'path' file is loaded as the code it is. With them the
	# handler's own profiles, the ones schema.toml lists: a 'path' file can
	# put its code under one of their names
	if not entries:
		return [], []
	from archinstoo.lib.profile.profiles_handler import ProfileHandler

	handler = ProfileHandler()
	stock = list(handler.profiles)
	tops = [
		profile
		for entry in entries
		if (profile := handler.parse_profile_config(entry))
	]
	return tops, stock


def _top_packages(top: Profile, stock: list[Profile]) -> set[str]:
	# mirrors Profile.install(): desktop and server strap themselves and their
	# selection, any other of the handler's profiles named as main straps
	# nothing. A 'path' profile is custom code: with an install() of its own
	# it is taken to strap like the former
	if top in stock:
		base = SCHEMA['profile_base'].get(top.name)
	elif type(top).install is not Profile.install:
		base = top.effective_packages()
	else:
		base = None
	if base is None:
		return set()

	pkgs = set(base)
	for sub in top.current_selection:
		# the schema where it lists the profile, the profile's own word where
		# it is custom code
		if sub not in stock or sub.name not in SCHEMA['profiles']:
			pkgs.update(sub.effective_packages())
			continue
		# free-form per profile, no TypedDict names these keys
		settings: dict[str, Any] = sub.custom_settings
		excluded = set(settings.get('excluded_packages') or [])
		pkgs.update(_profile_packages(sub.name, settings) - excluded)
		# seat_access, for the profiles that place its package (seat_packages)
		seat = settings.get('seat_access')
		if seat in sub.effective_packages():
			pkgs.add(seat)

	return pkgs


def _gfx_packages(gfx: str, custom: list[str], kernels: list[str]) -> set[str]:
	# mirrors profiles_handler.install_gfx_driver()
	if gfx not in SCHEMA['gfx_drivers']:
		return set()

	# a non-standard kernel swaps nvidia-open for its DKMS build: the whole
	# preset set from the schema, or the one package in a hand-picked list
	build = needs_dkms_build(kernels)
	dkms = SCHEMA['gfx_drivers_dkms'].get(gfx) if build else None

	if gfx == GfxDriver.Custom.value:
		# names outside the pool are dropped, as ArchConfig.from_config does
		pkgs = set(custom) & set(_flat('gfx_custom_choices'))
		if build and GfxPackage.NvidiaOpen.value in pkgs:
			pkgs.remove(GfxPackage.NvidiaOpen.value)
			pkgs.update(
				(GfxPackage.NvidiaOpenDkms.value, GfxPackage.Dkms.value)
			)
			pkgs.update(f'{k}-headers' for k in kernels)
	elif dkms:
		pkgs = set(dkms)
		pkgs.update(f'{k}-headers' for k in kernels)
	else:
		pkgs = set(SCHEMA['gfx_drivers'][gfx])

	return pkgs


def _pick(app: ApplicationSerialization, section: Section) -> set[str]:
	# walk the section's pick path into app_config. the value's shape says how
	# the section is read: a flag or a name takes a flat section whole, a name
	# indexes a table, a list unions its rows
	value: Any = app
	for key in section.pick:
		value = (value or {}).get(key)
		if value is None:
			return set()

	table: dict[str, list[str]] = SCHEMA[section.key]

	if 'packages' in table:
		return set(table['packages']) if value else set()
	if isinstance(value, list):
		return {p for name in value if name in table for p in table[name]}
	return set(table.get(value, []))


def _application_packages(app: ApplicationSerialization) -> set[str]:
	# every app_config category is a section with a pick; what follows is the
	# part a pick alone cannot say. schema_gen drags the installer in, so it
	# stays a function-local import like installer above
	from archinstoo.lib.schema_gen import SECTIONS

	pkgs: set[str] = set()
	for section in SECTIONS:
		if section.pick:
			pkgs.update(_pick(app, section))

	audio = app.get('audio_config')
	audio_name: str = audio.get('audio', '') if audio else ''
	if audio_name in SCHEMA['audio']:
		audio_fw = SCHEMA['audio_firmware']
		if SysInfo.requires_sof_fw():
			pkgs.update(audio_fw['sof'])
		if SysInfo.requires_alsa_fw():
			pkgs.update(audio_fw['alsa'])

	return pkgs


def collect(raw: ArchConfigSerialization) -> set[str]:
	# read the file the way the loader does: a null key is an unset one
	config: ArchConfigSerialization = strip_none(dict(raw))
	pkgs: set[str] = set()

	# base + firmware + whatever the host itself dictates
	pkgs.update(_flat('base'))
	pkgs.update(_firmware_packages(config))
	pkgs.update(_host_packages())

	# kernels: an empty list keeps the default, as ArchConfig.from_config does
	kernels = config.get('kernels') or [DEFAULT_KERNEL.value]
	pkgs.update(kernels)

	# kernel headers
	kernel_headers: bool = config.get('kernel_headers', False)
	if kernel_headers:
		pkgs.update(f'{k}-headers' for k in kernels)

	# bootloader
	bl = config.get('bootloader_config') or {}
	bl_name: str | None = bl.get('bootloader', '')
	bl_table = (
		SCHEMA['bootloaders']
		if SysInfo.has_uefi()
		else SCHEMA['bootloaders_bios']
	)
	if bl_name in bl_table:
		pkgs.update(bl_table[bl_name])

	# user packages
	for p in config.get('packages', []) or []:
		if p:
			pkgs.add(p)

	# profile: what install_profile_config straps, the selected profiles and
	# around them the X server and a greeter one of them supports
	pc = config.get('profile_config')
	tops, stock = _top_profiles((pc.get('profiles') if pc else None) or [])
	for top in tops:
		pkgs.update(_top_packages(top, stock))

	if any(DisplayServer.X11 in top.display_servers() for top in tops):
		pkgs.update(_flat('xorg_extra'))

	greeter: str | None = pc.get('greeter') if pc else None
	if greeter in SCHEMA['greeters'] and any(
		top.is_greeter_supported() for top in tops
	):
		pkgs.update(SCHEMA['greeters'][greeter])

	has_desktop = any(top.is_desktop_profile() for top in tops)

	pkgs.update(
		_gfx_packages(
			config.get('gfx_driver') or '',
			config.get('gfx_packages') or [],
			kernels,
		)
	)

	# network
	net = config.get('network_config')
	net_type: str = net.get('type', '') if net else ''
	if net_type in SCHEMA['network']:
		pkgs.update(SCHEMA['network'][net_type])
		if has_desktop and net_type in {NicType.NM.value, NicType.NM_IWD.value}:
			pkgs.update(_flat('network_desktop_extra'))
		# copy_iso_network_config() only adds iwd when the ISO has PSKs to carry
		if net_type == NicType.ISO.value and _iso_has_psks():
			pkgs.update(_flat('network_iso_extra'))

	# users: an entry without a username is none, as User.parse_arguments has
	# it. create_users wants the elevated one to have a password as well
	# (User.any_elevated). A saved config never holds one: the menu install it
	# was saved from did, and asks again before the next. So here an elevated
	# user counts as having theirs
	auth = config.get('auth_config') or {}
	users: list[UserSerialization] = []
	elevated = False
	for entry in auth.get('users') or []:
		# annotated: .get() takes any key, the type is what checks these two
		username: str | None = entry.get('username')
		elev: bool | None = entry.get('elev')
		if username:
			users.append(entry)
			elevated = elevated or elev is True

	# privilege escalation: create_users straps it once a user can use it
	priv_esc: str | None = auth.get(
		'privilege_escalation', PrivilegeEscalation.Sudo.value
	)
	if elevated and priv_esc in SCHEMA['privilege_escalation']:
		pkgs.update(SCHEMA['privilege_escalation'][priv_esc])

	pkgs.update(_application_packages(config.get('app_config') or {}))

	# shells (per-user in auth_config)
	for user in users:
		shell: str = user.get('shell', '')
		if shell in SCHEMA['shells']:
			pkgs.update(SCHEMA['shells'][shell])

	# filesystem tools, lvm
	disk = config.get('disk_config')
	pkgs.update(_filesystem_packages(disk) if disk else ())

	# console font: the ISO has terminus, the target only gets it on request
	font: str = (config.get('locale_config') or {}).get('console_font', '')
	if str(font).startswith('ter-'):
		pkgs.update(_flat('ter_fonts'))

	# snapshots: guided only sets them up on the default btrfs layout
	default_vols = _has_default_btrfs_vols(disk) if disk else False
	btrfs = (disk.get('btrfs_options') if disk and default_vols else None) or {}
	snapshot = btrfs.get('snapshot_config')
	snap_type: str = snapshot.get('type', '') if snapshot else ''
	if snap_type in SCHEMA['snapshots']:
		pkgs.update(SCHEMA['snapshots'][snap_type])
		# grub + btrfs snapshots
		if bl_name == Bootloader.Grub.value:
			pkgs.update(_flat('grub_extra'))

	# swap: only zram pulls a package, a swap file is plain tooling
	# a swap section defaults to zram on, as SwapConfiguration.parse_arg does
	swap = config.get('swap')
	zram: bool = swap.get('zram', True) if swap is not None else False
	if zram:
		pkgs.update(SCHEMA['swap'].get('zram', []))

	# grimoire builds AUR packages on the target, so its toolchain lands there.
	# an elevated user builds them, through sudo, doas or su: run0 needs a
	# booted system. The AUR packages themselves are in no repo, so nothing
	# here can resolve them
	aur: list[str] = config.get('aur_packages') or []
	if aur and elevated and priv_esc != PrivilegeEscalation.Run0.value:
		pkgs.update(_flat('aur_bootstrap'))

	stash_urls: list[list[str]] = [user.get('stash_urls') or [] for user in users]
	if any(stash_urls):
		pkgs.update(_flat('stash'))

	return pkgs


def _clean_dep(name: str) -> str | None:
	# Strip version constraints and filter out .so provides.
	if '.so' in name:
		return None
	# strip >=, <=, =, >, <
	for sep in ('>=', '<=', '=', '>', '<'):
		name = name.split(sep, 1)[0]
	return name or None


_TREE_PREFIX_RE = re.compile(r'^[\s│├└─]*')


def resolve_deps(
	explicit: set[str], target: str | None = None
) -> tuple[set[str], list[str]]:
	# Resolve the full dependency tree via `pactree -s`.
	#
	# `-s` keeps tree formatting and emits "<pkg> provides <virtual>" so we can
	# recover the real package name when a dep is satisfied by a .so virtual.
	# `-u` (unique) is omitted because it sometimes collapses such lines to the
	# bare virtual, hiding the providing package (e.g. networkmanager →
	# wpa_supplicant → pcsclite → polkit gets shown as just libpolkit-gobject-1.so).
	#
	# If `target` is given, also return explicit packages whose closure contains it.
	if not _requirements('pactree'):
		raise RequirementError('pactree not found; install pacman-contrib')

	explicit = expand(explicit)
	resolved: set[str] = set()
	roots_for_target: list[str] = []

	pkgs = sorted(explicit)
	total = len(pkgs)
	unresolved: list[str] = []

	for i, pkg in enumerate(pkgs, 1):
		deps: set[str] = set()
		try:
			output = SysCommand(f'pactree -s {pkg}')
			for line in output:
				raw = line.decode().rstrip()
				if not raw:
					continue
				m = _TREE_PREFIX_RE.match(raw)
				rest = raw[m.end() if m else 0 :].split(
					' provides ', 1
				)[0]
				if name := _clean_dep(rest):
					deps.add(name)
		except Exception:
			# counted as a leaf: the estimate below is a lower bound
			deps.add(pkg)
			unresolved.append(pkg)

		resolved.update(deps)
		if target and pkg != target and target in deps:
			roots_for_target.append(pkg)

		print(
			f'\r  {i}/{total} | resolved: {len(resolved)}',
			end='',
			flush=True,
		)

	print()
	if unresolved:
		print(
			f'  {len(unresolved)} package(s) could not be resolved, sizes '
			f'are a lower bound: {" ".join(unresolved)}',
			file=sys.stderr,
		)
	return resolved, roots_for_target
