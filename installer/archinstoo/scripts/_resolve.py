# Shared package-set resolution for the count and size scripts.
#
# collect() turns a saved config into its explicit package set; resolve_deps()
# expands pacman groups, then the full dependency tree via pactree
# (pacman-contrib). Kept free of a module-level entrypoint so both scripts can
# import it without side effects.

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from archinstoo.default_profiles.desktops import DEFAULT_TERMINAL
from archinstoo.lib.exceptions import RequirementError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.hardware import CpuVendor, GfxDriver, SysInfo
from archinstoo.lib.models import firmware as firmware_model
from archinstoo.lib.models.device import FilesystemType
from archinstoo.lib.models.firmware import FirmwareType
from archinstoo.lib.models.network import NicType
from archinstoo.lib.pm.groups import expand
from archinstoo.lib.schema import SCHEMA
from archinstoo.lib.utils.env import Os

if TYPE_CHECKING:
	from archinstoo.lib.profile.base import Profile
	from archinstoo.lib.profile.profiles_handler import ProfileSerialization


def _flat(key: str) -> list[str]:
	# sections that are one list rather than a map of options hold it under
	# `packages` (see lib/schema_gen.py for why every section is a table)
	packages: list[str] = SCHEMA[key]['packages']
	return packages


def _requirements(*binaries: str) -> bool:
	try:
		for name in binaries:
			Os.locate_binary(name)
		return True
	except RequirementError:
		return False


def _firmware_packages(config: dict[str, Any]) -> set[str]:
	# mirrors FirmwareConfiguration.packages(): the schema holds what is static,
	# the vendor list comes from the config and FULL's optdeps from the host
	firmware_cfg = config.get('firmware') or {}
	firmware_type = firmware_cfg.get('firmware_type', FirmwareType.FULL.value)
	pkgs = set(SCHEMA['firmware'].get(firmware_type, []))

	if firmware_type == FirmwareType.VENDOR.value:
		pkgs.update(firmware_cfg.get('vendors', []) or [])
	elif firmware_type == FirmwareType.FULL.value:
		# through the module so a test can pin the detection, as gfx does
		pkgs.update(v.value for v in firmware_model.detect_optdeps())

	return pkgs


def _iso_has_psks() -> bool:
	# mirrors copy_iso_network_config(): the target only needs iwd when there
	# are ISO PSKs to carry over
	return bool(list(Path('/var/lib/iwd').glob('*.psk')))


def _host_packages() -> set[str]:
	# what the installer reads off the running system rather than the config;
	# count and size run on that same host, so the detection carries over
	pkgs: set[str] = set()

	# installer.py:accessibility_tools_in_use, imported late: it lives in
	# installer.py, which drags in pyparted and the rest of the runtime
	from archinstoo.lib.installer import accessibility_tools_in_use

	if accessibility_tools_in_use():
		pkgs.update(_flat('accessibility'))

	if not SysInfo.is_vm() and (vendor := SysInfo.cpu_vendor()):
		pkgs.update(SCHEMA['microcode'].get(vendor.value, []))

	return pkgs


def _filesystem_packages(disk: dict[str, Any], kernels: list[str]) -> set[str]:
	# minimal_installation() prepares LVM volumes or partitions, never both, and
	# lvm_config sits next to device_modifications rather than inside them
	fs_tools = SCHEMA['filesystem_tools']
	fs_types: set[str] = set()
	lvm_config = disk.get('lvm_config') or {}

	if lvm_config:
		for group in lvm_config.get('vol_groups', []) or []:
			for vol in group.get('volumes', []) or []:
				fs_types.add(vol.get('fs_type', ''))
	else:
		for dev in disk.get('device_modifications', []) or []:
			for part in dev.get('partitions', []) or []:
				fs_types.add(part.get('fs_type', ''))

	pkgs = {p for fs in fs_types if fs in fs_tools for p in fs_tools[fs]}

	if lvm_config:
		pkgs.update(_flat('lvm'))

	# out-of-tree module, built per kernel
	if FilesystemType.BCACHEFS.value in fs_types:
		pkgs.update(_flat('bcachefs_extra'))
		pkgs.update(f'{k}-headers' for k in kernels)

	return pkgs


def _development_packages(dev: dict[str, Any]) -> set[str]:
	# development_config nests two à-la-carte tool lists; resolve both against the schema
	pkgs: set[str] = set()
	for section, schema_key in (('language_config', 'languages'), ('devtool_config', 'devtools')):
		for tool in (dev.get(section) or {}).get('tools', []) or []:
			if tool in SCHEMA[schema_key]:
				pkgs.update(SCHEMA[schema_key][tool])
	return pkgs


def _profile_packages(name: str, settings: dict[str, Any]) -> set[str]:
	prof_pkgs = set(SCHEMA['profiles'][name])

	# <name>_compositor swaps the default (niri) compositor set
	if comp_sets := SCHEMA['compositors'].get(name):
		comps = settings.get(f'{name}_compositor') or ['niri']
		if isinstance(comps, str):
			comps = [comps]
		prof_pkgs.difference_update(comp_sets['niri'])
		for comp in comps:
			prof_pkgs.update(comp_sets.get(comp, []))

	return prof_pkgs


def _path_profiles(top_profiles: list[ProfileSerialization]) -> list[Profile]:
	# custom 'path' profiles are code, not schema entries; load them the same
	# way the installer does so their packages and desktop-typing count too
	entries = [tp for tp in top_profiles if tp.get('path')]
	if not entries:
		return []
	from archinstoo.lib.profile.profiles_handler import ProfileHandler

	handler = ProfileHandler()
	return [profile for tp in entries if (profile := handler.parse_profile_config(tp))]


def _gfx_packages(gfx: str, kernels: list[str], details: list[str]) -> set[str]:
	# mirrors profiles_handler.install_gfx_driver(): the driver set, then the
	# X11 half if any selected profile needs it
	if gfx not in SCHEMA['gfx_drivers']:
		return set()

	# a non-standard kernel swaps the whole driver set for its DKMS build
	dkms = SCHEMA['gfx_drivers_dkms'].get(gfx) if any('-' in k for k in kernels) else None
	if dkms:
		pkgs = set(dkms)
		pkgs.update(f'{k}-headers' for k in kernels)
	else:
		pkgs = set(SCHEMA['gfx_drivers'][gfx])

	# the generic driver picks its vulkan layer off the host GPU, the way the
	# microcode does; count and size run on that same host
	if gfx == GfxDriver.MesaOpenSource.value:
		mesa_extra = SCHEMA['gfx_mesa_extra']
		if SysInfo.has_intel_graphics():
			pkgs.update(mesa_extra[CpuVendor.GenuineIntel.value])
		elif SysInfo.has_amd_graphics():
			pkgs.update(mesa_extra[CpuVendor.AuthenticAMD.value])

	if set(details) & set(SCHEMA['xorg_profiles']['profiles']):
		pkgs.update(_flat('xorg_extra'))

	return pkgs


def _terminal_packages(app: dict[str, Any], details: list[str]) -> set[str]:
	# one terminal, shared by every profile in terminal_profiles. TerminalApp
	# installs the pick; a skipped menu entry leaves those profiles on the
	# default, which install_profile_config() installs instead
	terminal = (app.get('terminal_config') or {}).get('terminal', '')

	if terminal not in SCHEMA['terminals']:
		if not set(details) & set(SCHEMA['terminal_profiles']['profiles']):
			return set()
		terminal = DEFAULT_TERMINAL

	return set(SCHEMA['terminals'][terminal])


def _application_packages(app: dict[str, Any], details: list[str]) -> set[str]:
	# every app_config section that pulls packages. the result is a set, so the
	# à-la-carte ones are grouped by shape rather than by install order
	pkgs: set[str] = set()

	if (app.get('bluetooth_config') or {}).get('enabled', False):
		pkgs.update(_flat('bluetooth'))

	audio = (app.get('audio_config') or {}).get('audio', '')
	if audio in SCHEMA['audio']:
		pkgs.update(SCHEMA['audio'][audio])
		audio_fw = SCHEMA['audio_firmware']
		if SysInfo.requires_sof_fw():
			pkgs.update(audio_fw['sof'])
		if SysInfo.requires_alsa_fw():
			pkgs.update(audio_fw['alsa'])

	# option -> section, for the categories that are a single pick
	for key, field, section in (
		('power_management_config', 'power_management', 'power_management'),
		('firewall_config', 'firewall', 'firewalls'),
		('monitor_config', 'monitor', 'monitors'),
		('editor_config', 'editor', 'editors'),
	):
		choice = (app.get(key) or {}).get(field, '')
		if choice in SCHEMA[section]:
			pkgs.update(SCHEMA[section][choice])

	if app.get('cpu_scheduler_config'):
		pkgs.update(_flat('cpu_scheduler'))

	if (app.get('print_service_config') or {}).get('enabled', False):
		pkgs.update(_flat('printing'))

	# and the ones that are a multi-select
	for key, section in (('management_config', 'management'), ('security_config', 'security')):
		for tool in (app.get(key) or {}).get('tools', []) or []:
			if tool in SCHEMA[section]:
				pkgs.update(SCHEMA[section][tool])

	pkgs.update(_terminal_packages(app, details))
	pkgs.update(_development_packages(app.get('development_config') or {}))

	return pkgs


def collect(config: dict[str, Any]) -> set[str]:
	pkgs: set[str] = set()

	# base + firmware + whatever the host itself dictates
	pkgs.update(_flat('base'))
	pkgs.update(_firmware_packages(config))
	pkgs.update(_host_packages())

	# kernels
	kernels = config.get('kernels', ['linux'])
	pkgs.update(kernels)

	# kernel headers
	if config.get('kernel_headers', False):
		pkgs.update(f'{k}-headers' for k in kernels)

	# bootloader
	bl = config.get('bootloader_config') or {}
	bl_name = bl.get('bootloader', '')
	if bl_name in SCHEMA['bootloaders']:
		pkgs.update(SCHEMA['bootloaders'][bl_name])

	# user packages
	for p in config.get('packages', []) or []:
		if p:
			pkgs.add(p)

	# profile
	pc = config.get('profile_config') or {}
	top_profiles = pc.get('profiles') or []
	profiles = SCHEMA['profiles']
	mains: set[str] = set()
	details: list[str] = []

	for tp in top_profiles:
		main = tp.get('main', '')
		if main:
			mains.add(main)
			# desktop and server carry different base sets
			pkgs.update(SCHEMA['profile_base'].get(main, []))

		tp_details = tp.get('details', []) or []
		details.extend(tp_details)
		custom_settings = tp.get('custom_settings') or {}

		for name in tp_details:
			settings = custom_settings.get(name) or {}
			excluded = set(settings.get('excluded_packages') or [])

			if name in profiles:
				pkgs.update(p for p in _profile_packages(name, settings) if p not in excluded)

			# seat_access for sway/river/niri/labwc/dms
			if (seat := settings.get('seat_access')) and seat not in excluded:
				pkgs.add(seat)

	# custom path profiles: own packages plus selections, exclusions applied,
	# mirroring Profile.install() (self + current_selection effective_packages)
	custom_profiles = _path_profiles(top_profiles)
	for profile in custom_profiles:
		pkgs.update(profile.effective_packages())
		for sub in profile.current_selection:
			pkgs.update(sub.effective_packages())

	has_desktop = 'desktop' in mains or any(p.is_desktop_profile() for p in custom_profiles)

	main = next(iter(mains), '')

	# greeter
	greeter = pc.get('greeter', '')
	if greeter in SCHEMA['greeters']:
		pkgs.update(SCHEMA['greeters'][greeter])

	pkgs.update(_gfx_packages(pc.get('gfx_driver', ''), kernels, details))

	# network
	net = config.get('network_config') or {}
	net_type = net.get('type', '')
	if net_type in SCHEMA['network']:
		pkgs.update(SCHEMA['network'][net_type])
		if has_desktop and net_type in (NicType.NM.value, NicType.NM_IWD.value):
			pkgs.update(_flat('network_desktop_extra'))
		# copy_iso_network_config() only adds iwd when the ISO has PSKs to carry
		if net_type == NicType.ISO.value and _iso_has_psks():
			pkgs.update(_flat('network_iso_extra'))

	# privilege escalation
	auth = config.get('auth_config') or {}
	priv_esc = auth.get('privilege_escalation', 'sudo')
	if priv_esc in SCHEMA['privilege_escalation']:
		pkgs.update(SCHEMA['privilege_escalation'][priv_esc])

	pkgs.update(_application_packages(config.get('app_config') or {}, details))

	# shells (per-user in auth_config)
	users = auth.get('users', []) or []
	for user in users:
		shell = user.get('shell', '')
		if shell in SCHEMA['shells']:
			pkgs.update(SCHEMA['shells'][shell])

	# filesystem tools, lvm
	disk = config.get('disk_config') or {}
	pkgs.update(_filesystem_packages(disk, kernels))

	# console font: the ISO has terminus, the target only gets it on request
	if str((config.get('locale_config') or {}).get('console_font', '')).startswith('ter-'):
		pkgs.update(_flat('ter_fonts'))

	# snapshots
	btrfs = disk.get('btrfs_options') or {}
	snapshot = btrfs.get('snapshot_config') or {}
	snap_type = snapshot.get('type', '')
	if snap_type in SCHEMA['snapshots']:
		pkgs.update(SCHEMA['snapshots'][snap_type])
		# grub + btrfs snapshots
		if bl_name == 'grub':
			pkgs.update(_flat('grub_extra'))

	# swap: only zram pulls a package, a swap file is plain tooling
	swap = config.get('swap') or {}
	if swap.get('zram', False):
		pkgs.update(SCHEMA['swap'].get('zram', []))

	# grimoire builds AUR packages on the target, so its toolchain lands there.
	# it needs an elevated user to build as, and the AUR packages themselves are
	# in no repo, so nothing here can size them
	if config.get('aur_packages') and any(user.get('elev') for user in users):
		pkgs.update(_flat('aur_bootstrap'))

	if any(user.get('stash_urls') for user in users):
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


def resolve_deps(explicit: set[str], target: str | None = None) -> tuple[set[str], list[str]]:
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

	for i, pkg in enumerate(pkgs, 1):
		deps: set[str] = set()
		try:
			output = SysCommand(f'pactree -s {pkg}')
			for line in output:
				raw = line.decode().rstrip()
				if not raw:
					continue
				m = _TREE_PREFIX_RE.match(raw)
				rest = raw[m.end() if m else 0 :].split(' provides ', 1)[0]
				if name := _clean_dep(rest):
					deps.add(name)
		except Exception:
			deps.add(pkg)

		resolved.update(deps)
		if target and pkg != target and target in deps:
			roots_for_target.append(pkg)

		print(f'\r  {i}/{total} | resolved: {len(resolved)}', end='', flush=True)

	print()
	return resolved, roots_for_target
