# Generate schema.toml from the installer's own package definitions.
#
# Flattening what an install can pull into plain tables lets two tools read it
# without the runtime: scripts/_resolve.py (count, size), which expands a saved
# config, and nvchecker/NVGEN, which version-tracks every package we can touch.
# Generating rather than transcribing is what keeps them from disagreeing with
# the install; tests/test_schema.py fails when the committed file goes stale.
#
# Sections come out in the order the install runs them: each names the call in
# scripts/guided.py:perform_installation that straps it, and render() sorts by
# where that call sits in the source. Reorder guided.py and the schema follows;
# nothing here is hand-ordered past the sections sharing one call.
#
#     python -m archinstoo --script schema

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, override

from archinstoo.lib import installer
from archinstoo.lib.applications.cat.audio import AudioApp
from archinstoo.lib.applications.cat.bluetooth import BluetoothApp
from archinstoo.lib.applications.cat.cpu_scheduler import CPUSchedulerApp
from archinstoo.lib.applications.cat.firewall import FirewallApp
from archinstoo.lib.applications.cat.media_codecs import MediaCodecsApp
from archinstoo.lib.applications.cat.power_management import PowerManagementApp
from archinstoo.lib.applications.cat.print_service import PrintServiceApp
from archinstoo.lib.applications.cat.security import SecurityApp
from archinstoo.lib.applications.cat.thunderbolt import ThunderboltApp
from archinstoo.lib.hardware import GFX_CUSTOM_CHOICES, GFX_PACKAGES, MESA_HOST_EXTRA, XORG_EXTRA, CpuVendor, GfxDriver
from archinstoo.lib.models.application import (
	Audio,
	DevTool,
	Editor,
	Firewall,
	Language,
	Management,
	Monitor,
	PowerManagement,
	Security,
	Terminal,
)
from archinstoo.lib.models.authentication import PrivilegeEscalation
from archinstoo.lib.models.bootloader import Bootloader
from archinstoo.lib.models.device import FilesystemType, SnapshotType
from archinstoo.lib.models.firmware import FULL_FIRMWARE, FirmwareType
from archinstoo.lib.models.network import ISO_PSK_EXTRA, NM_DESKTOP_EXTRA, NicType
from archinstoo.lib.models.users import Shell
from archinstoo.lib.profile.base import DisplayServer, GreeterType, ProfileType, SeatAccess
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.lib.schema import SCHEMA_PATH

if TYPE_CHECKING:
	from collections.abc import Callable
	from enum import StrEnum

	from archinstoo.lib.profile.base import Profile

Packages = list[str]
Table = dict[str, Packages]
# a section is one flat list, a table of them, or one table per profile
Value = Packages | Table | dict[str, Table]

# a non-standard kernel is what flips a driver to its DKMS variant
_DKMS_KERNEL = ['linux-zen']

# leaf profiles map 1:1 to the profiles table; the rest (desktop/server/xorg/
# minimal) are the abstract tops the handler also discovers
_LEAF_PROFILES = {ProfileType.DesktopEnv, ProfileType.WindowMgr, ProfileType.ServerType}


def _leaves() -> list[Profile]:
	return [p for p in ProfileHandler().profiles if p.profile_type in _LEAF_PROFILES]


def _one_to_one(enum: type[StrEnum]) -> Table:
	# categories the installer expands as [tool.value for tool in tools], so
	# every option is its own package
	return {e.value: [e.value] for e in enum}


@dataclass(frozen=True)
class Section:
	key: str
	doc: str
	value: Callable[[], Value]
	# the call in perform_installation that straps this section, by method or
	# function name. sections sharing one keep their order below, which is the
	# order inside that method (minimal_installation, install_applications)
	site: str
	# key a flat list renders under, since every section has to be a table (see
	# _HEADER). `profiles` marks names rather than packages, so version tracking
	# can skip them
	list_key: str = 'packages'
	# where a saved config keeps the choice this section answers, as a key path
	# under app_config. _resolve walks these instead of naming each category
	# again: a flag or a name takes a flat section whole, a name indexes a
	# table, a list unions its rows. tests/test_schema.py holds every
	# app_config category to having one
	pick: tuple[str, ...] = ()


SECTIONS: tuple[Section, ...] = (
	Section('base', 'the seed of every pacstrap', lambda: installer.__base_packages__, site='Installer'),
	Section(
		'firmware',
		'the static half: `vendor` takes its packages from the saved config,\n`full` adds the optdeps matched against the host PCI/USB IDs',
		lambda: {
			FirmwareType.FULL.value: FULL_FIRMWARE,
			FirmwareType.MINIMAL.value: [],
			FirmwareType.VENDOR.value: [],
		},
		site='Installer',
	),
	Section(
		'accessibility',
		'a live ISO with accessibility active installs these onto the target',
		lambda: installer.__accessibility_packages__,
		site='Installer',
	),
	Section('lvm', 'any lvm layout', lambda: installer.__lvm_packages__, site='minimal_installation'),
	Section(
		'filesystem_tools',
		'base already covers e2fsprogs and dosfstools; these are the rest',
		lambda: {fs.value: [pkg] for fs in FilesystemType if (pkg := fs.installation_pkg)},
		site='minimal_installation',
	),
	Section(
		'bcachefs_extra',
		'out of tree: built per kernel, so every kernel also pulls its -headers',
		lambda: installer.__bcachefs_packages__,
		site='minimal_installation',
	),
	Section(
		'fido2',
		'sd-encrypt only bundles the fido2 dlopen libs if this is present when the\n'
		'initramfs is built. never reachable from a saved config: the password\n'
		'would have to be saved with it',
		lambda: installer.__fido2_packages__,
		site='minimal_installation',
	),
	Section(
		'microcode',
		'picked from the detected CPU; VMs get none',
		lambda: {v.value: [ucode.stem] for v in CpuVendor if (ucode := v.get_ucode())},
		site='minimal_installation',
	),
	Section('ter_fonts', 'to match the ISO when `ter-` console fonts are chosen', lambda: installer.__ter_font_packages__, site='minimal_installation'),
	Section(
		'swap',
		'only zram pulls a package: a hibernation swapfile is mkswap (util-linux,\na base dep) or btrfs-progs, both already covered',
		lambda: {'zram': installer.__zram_packages__},
		site='setup_swap',
	),
	Section(
		'privilege_escalation',
		'run0 is part of systemd and only needs polkit',
		lambda: {p.value: p.packages() for p in PrivilegeEscalation},
		site='create_users',
	),
	Section('stash', 'cloning a user stash', lambda: installer.__stash_packages__, site='create_users'),
	Section(
		'shells',
		'bash is default and rbash is bash restricted, so neither needs a package',
		lambda: {s.value: s.packages for s in Shell},
		site='ShellApp',
	),
	Section('bluetooth', '', lambda: BluetoothApp().packages, pick=('bluetooth_config', 'enabled'), site='install_applications'),
	Section(
		'thunderbolt',
		'only shown with a thunderbolt/usb4 host controller; boltd is dbus\nactivated, no service to enable',
		lambda: ThunderboltApp().packages,
		pick=('thunderbolt_config', 'enabled'),
		site='install_applications',
	),
	Section(
		'audio',
		'',
		lambda: {
			Audio.PIPEWIRE.value: AudioApp().pipewire_packages,
			Audio.PULSEAUDIO.value: AudioApp().pulseaudio_packages,
		},
		pick=('audio_config', 'audio'),
		site='install_applications',
	),
	Section(
		'audio_firmware',
		'added with either audio server when the matching driver is loaded',
		lambda: {'sof': AudioApp().sof_packages, 'alsa': AudioApp().alsa_packages},
		site='install_applications',
	),
	Section(
		'media_codecs',
		'the codec half of eos-base-group; gstreamer core, base, good and ffmpeg\ncome in as deps',
		lambda: MediaCodecsApp().packages,
		pick=('media_codecs_config', 'enabled'),
		site='install_applications',
	),
	Section(
		'power_management',
		'only shown on laptops',
		lambda: {
			PowerManagement.PPD.value: PowerManagementApp().ppd_packages,
			PowerManagement.TUNED.value: PowerManagementApp().tuned_packages,
		},
		pick=('power_management_config', 'power_management'),
		site='install_applications',
	),
	Section(
		'cpu_scheduler',
		'sched_ext: one set, the choice only picks which binary scx_loader starts',
		lambda: CPUSchedulerApp().packages,
		pick=('cpu_scheduler_config', 'scheduler'),
		site='install_applications',
	),
	Section(
		'printing',
		'ghostscript is the PostScript interpreter cups needs for most drivers',
		lambda: PrintServiceApp().packages,
		pick=('print_service_config', 'enabled'),
		site='install_applications',
	),
	Section(
		'firewalls',
		'',
		lambda: {
			Firewall.UFW.value: FirewallApp().ufw_packages,
			Firewall.FWD.value: FirewallApp().fwd_packages,
		},
		pick=('firewall_config', 'firewall'),
		site='install_applications',
	),
	Section('management', '', lambda: _one_to_one(Management), pick=('management_config', 'tools'), site='install_applications'),
	Section('monitors', '', lambda: _one_to_one(Monitor), pick=('monitor_config', 'monitor'), site='install_applications'),
	Section(
		'editors',
		'EDITOR lands in /etc/environment; only vi is not named after the option',
		lambda: {e.value: e.packages for e in Editor},
		pick=('editor_config', 'editor'),
		site='install_applications',
	),
	Section(
		'terminals',
		'one choice, shared by every profile in terminal_profiles. package and\nbinary share a name, and TERMINAL lands in /etc/environment',
		lambda: {t.value: t.packages for t in Terminal},
		pick=('terminal_config', 'terminal'),
		site='install_applications',
	),
	Section(
		'security',
		'three carry extra configuration, the rest install themselves',
		lambda: {
			Security.APPARMOR.value: SecurityApp().apparmor_packages,
			Security.FIREJAIL.value: SecurityApp().firejail_packages,
			Security.BUBBLEWRAP.value: SecurityApp().bubblewrap_packages,
			**{s.value: [s.value] for s in Security if s not in (Security.APPARMOR, Security.FIREJAIL, Security.BUBBLEWRAP)},
		},
		pick=('security_config', 'tools'),
		site='install_applications',
	),
	Section('languages', '', lambda: _one_to_one(Language), pick=('development_config', 'language_config', 'tools'), site='install_applications'),
	Section('devtools', '', lambda: _one_to_one(DevTool), pick=('development_config', 'devtool_config', 'tools'), site='install_applications'),
	Section('snapshots', '', lambda: {s.value: s.packages for s in SnapshotType}, site='setup_btrfs_snapshot'),
	Section('grub_extra', 'grub plus either snapshot tool adds these', lambda: installer.__grub_snapshot_packages__, site='setup_btrfs_snapshot'),
	Section(
		'bootloaders',
		'the UEFI set; a BIOS install skips efibootmgr, and refind never needs it',
		lambda: {b.value: b.packages() for b in Bootloader},
		site='add_bootloader',
	),
	Section(
		'network',
		'iso and manual configure systemd-networkd/resolved, both part of base',
		lambda: {n.value: n.packages for n in NicType},
		site='install_network_config',
	),
	Section(
		'network_desktop_extra',
		'NetworkManager on a desktop profile also gets its tray applet',
		lambda: NM_DESKTOP_EXTRA,
		site='install_network_config',
	),
	Section(
		'network_iso_extra',
		'the ISO config carries iwd PSKs over, and the target needs iwd to read them',
		lambda: ISO_PSK_EXTRA,
		site='install_network_config',
	),
	Section(
		'gfx_drivers',
		'added before desktops, which may depend on a virtual vulkan-something.\nlibva-mesa-driver is provided by mesa since 24.2.7',
		lambda: {d.value: [p.value for p in GFX_PACKAGES[d]] for d in GfxDriver},
		site='install_profile_config',
	),
	Section(
		'gfx_custom_choices',
		'the pool the custom driver picks from, one package per tick; the dkms\nswap and xorg are derived the same way as for the presets',
		lambda: [p.value for p in GFX_CUSTOM_CHOICES],
		site='install_profile_config',
	),
	Section(
		'gfx_drivers_dkms',
		'what a driver installs instead when a non-standard kernel needs a build',
		lambda: {d.value: [p.value for p in d.gfx_packages(_DKMS_KERNEL)] for d in GfxDriver if d.has_dkms_variant()},
		site='install_profile_config',
	),
	Section(
		'gfx_mesa_extra',
		'the generic driver adds a vulkan layer for whatever GPU the host has',
		lambda: {vendor: [p.value for p in pkgs] for vendor, pkgs in MESA_HOST_EXTRA.items()},
		site='install_profile_config',
	),
	Section(
		'xorg_extra',
		'the X11 half, added off DisplayServer rather than off the driver',
		lambda: [p.value for p in XORG_EXTRA],
		site='install_profile_config',
	),
	Section(
		'xorg_profiles',
		'pull xorg_extra when a gfx driver is selected, i.e. every XorgProfile',
		lambda: [p.name for p in _leaves() if DisplayServer.X11 in p.display_servers()],
		list_key='profiles',
		site='install_profile_config',
	),
	Section(
		'profile_base',
		'always installed alongside a top-level profile',
		lambda: {p.name: p.packages for p in ProfileHandler().profiles if p.profile_type in (ProfileType.Desktop, ProfileType.Server)},
		site='install_profile_config',
	),
	Section(
		'profiles',
		'every desktop, window manager and server profile. one listed in\nterminal_profiles has none here: that comes from the shared choice',
		lambda: {p.name: p.packages for p in _leaves()},
		site='install_profile_config',
	),
	Section(
		'terminal_profiles',
		'ship a keybind rather than a terminal. install_profile_config() installs\nthe choice once for these, or the default when the menu was skipped',
		lambda: [p.name for p in _leaves() if p.needs_terminal],
		list_key='profiles',
		site='install_profile_config',
	),
	Section(
		'compositors',
		"profiles that run on a compositor of the user's choosing. their entry\n"
		'above bakes in the niri default, a <name>_compositor custom_setting swaps it',
		lambda: {p.name: p.compositor_packages for p in _leaves() if p.compositor_packages},
		site='install_profile_config',
	),
	Section(
		'seat_access',
		'per-profile seat_access custom_setting; the value is the package',
		lambda: {s.name: [s.value] for s in SeatAccess},
		site='install_profile_config',
	),
	Section(
		'greeters',
		'each desktop names a default; None (null in a config) is always available',
		lambda: {g.value: g.packages for g in GreeterType},
		site='install_profile_config',
	),
	Section(
		'aur_bootstrap',
		'what grimoire needs on the target to build from the AUR. the AUR packages\nthemselves are in no repo, so nothing can size them',
		lambda: installer.__aur_bootstrap_packages__,
		site='run_grimoire_installation',
	),
)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_HEADER = """\
# schema.toml - generated, do not edit.
#
# The package sets an archinstoo install can pull, flattened out of the code
# that installs them. Read by scripts/_resolve.py (count, size) and by
# nvchecker/NVGEN, neither of which should have to guess.
#
# Sections follow the order the install runs them, banners naming the call in
# scripts/guided.py:perform_installation. Every section is a table so
# that order survives: a top-level `key = [...]` after the first [header] would
# silently nest under it. A section that is one flat list holds it under
# `packages`, or `profiles` where the names are profiles rather than packages.
#
# To change what a section holds, change the codepath named above it, then:
#
#     python -m archinstoo --script schema
"""


def _key(name: str) -> str:
	# TOML bare keys allow letters, digits, - and _; anything else gets quoted
	ok = name and all(c.isalnum() or c in '-_' for c in name)
	return name if ok else json.dumps(name)


def _list(values: list[str]) -> str:
	return '[' + ', '.join(json.dumps(v) for v in values) + ']'


def _comment(doc: str) -> list[str]:
	return [f'# {line}' if line else '#' for line in doc.splitlines()] if doc else []


def _tables(section: Section) -> list[tuple[str, Table]]:
	# (header, table) pairs. a flat list becomes one table under list_key; a
	# nested value (compositors) becomes one [section.name] table per profile
	value = section.value()
	if isinstance(value, list):
		return [(_key(section.key), {section.list_key: value})]

	flat: Table = {}
	nested: list[tuple[str, Table]] = []
	for name, entry in value.items():
		if isinstance(entry, dict):
			nested.append((f'{_key(section.key)}.{_key(name)}', entry))
		else:
			flat[name] = entry

	return nested or [(_key(section.key), flat)]


_GUIDED = Path(__file__).parents[1] / 'scripts' / 'guided.py'


class _Calls(ast.NodeVisitor):
	# every call in perform_installation, in source order, by the name called:
	# the method for `x.f()`, the function or class for `f()`
	def __init__(self) -> None:
		self.order: list[str] = []

	@override
	def visit_Call(self, node: ast.Call) -> None:
		func = node.func
		name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', None)
		if name and name not in self.order:
			self.order.append(name)
		self.generic_visit(node)


def site_order() -> list[str]:
	tree = ast.parse(_GUIDED.read_text())
	fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'perform_installation')
	calls = _Calls()
	calls.visit(fn)
	return calls.order


def ordered() -> list[Section]:
	# SECTIONS in install order. a site perform_installation no longer calls
	# is a rename or a dropped step, either way the section has to follow
	order = site_order()
	missing = sorted({s.site for s in SECTIONS} - set(order))
	if missing:
		raise ValueError(f'sites not called in perform_installation: {missing}')
	return sorted(SECTIONS, key=lambda s: order.index(s.site))


def render() -> str:
	lines = [_HEADER]

	site = None
	for section in ordered():
		if section.site != site:
			site = section.site
			lines.append(f'# -- {site} --')
		lines += _comment(section.doc)
		for header, table in _tables(section):
			lines.append(f'[{header}]')
			lines += [f'{_key(name)} = {_list(pkgs)}' for name, pkgs in table.items()]
			lines.append('')

	return '\n'.join(lines)


def write(path: Path = SCHEMA_PATH) -> None:
	path.write_text(render())
