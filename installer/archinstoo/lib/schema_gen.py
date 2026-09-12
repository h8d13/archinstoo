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
from archinstoo.lib.applications.cat.flatpak import FlatpakApp
from archinstoo.lib.applications.cat.media_codecs import MediaCodecsApp
from archinstoo.lib.applications.cat.power_management import PowerManagementApp
from archinstoo.lib.applications.cat.print_service import PrintServiceApp
from archinstoo.lib.applications.cat.security import SecurityApp
from archinstoo.lib.applications.cat.thunderbolt import ThunderboltApp
from archinstoo.lib.authentication import stash
from archinstoo.lib.disk import snapshots, swap
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
from archinstoo.lib.pm import aur
from archinstoo.lib.profile.base import GreeterType, ProfileType, SeatAccess
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
	value: Callable[[], Value]
	# the call in perform_installation that straps this section, as written
	# there. sections sharing one keep their order below, which is the order
	# inside that method (minimal_installation, install_applications)
	site: str
	# where a saved config keeps the choice this section answers, as a key path
	# under app_config. _resolve walks these instead of naming each category
	# again: a flag or a name takes a flat section whole, a name indexes a
	# table, a list unions its rows. tests/test_schema.py holds every
	# app_config category to having one
	pick: tuple[str, ...] = ()


SECTIONS: tuple[Section, ...] = (
	Section('base', lambda: installer.__base_packages__, site='Installer'),
	Section(
		'firmware',
		lambda: {
			FirmwareType.FULL.value: FULL_FIRMWARE,
			FirmwareType.MINIMAL.value: [],
			FirmwareType.VENDOR.value: [],
		},
		site='Installer',
	),
	Section(
		'accessibility',
		lambda: installer.__accessibility_packages__,
		site='Installer',
	),
	Section('lvm', lambda: installer.__lvm_packages__, site='installation.minimal_installation'),
	Section(
		'filesystem_tools',
		lambda: {fs.value: [pkg] for fs in FilesystemType if (pkg := fs.installation_pkg)},
		site='installation.minimal_installation',
	),
	Section(
		'bcachefs_extra',
		lambda: installer.__bcachefs_packages__,
		site='installation.minimal_installation',
	),
	Section(
		'fido2',
		lambda: installer.__fido2_packages__,
		site='installation.minimal_installation',
	),
	Section(
		'microcode',
		lambda: {v.value: [ucode.stem] for v in CpuVendor if (ucode := v.get_ucode())},
		site='installation.minimal_installation',
	),
	Section('ter_fonts', lambda: installer.__ter_font_packages__, site='installation.minimal_installation'),
	Section(
		'swap',
		lambda: {'zram': swap.__zram_packages__},
		site='installation.setup_swap',
	),
	Section(
		'privilege_escalation',
		lambda: {p.value: p.packages() for p in PrivilegeEscalation},
		site='installation.create_users',
	),
	Section('stash', lambda: stash.__stash_packages__, site='installation.create_users'),
	Section(
		'shells',
		lambda: {s.value: s.packages for s in Shell},
		site='ShellApp().install',
	),
	Section('bluetooth', lambda: BluetoothApp().packages, pick=('bluetooth_config', 'enabled'), site='application_handler.install_applications'),
	Section(
		'thunderbolt',
		lambda: ThunderboltApp().packages,
		pick=('thunderbolt_config', 'enabled'),
		site='application_handler.install_applications',
	),
	Section(
		'audio_firmware',
		lambda: {'sof': AudioApp().sof_packages, 'alsa': AudioApp().alsa_packages},
		site='application_handler.install_applications',
	),
	Section(
		'audio',
		lambda: {
			Audio.PIPEWIRE.value: AudioApp().pipewire_packages,
			Audio.PULSEAUDIO.value: AudioApp().pulseaudio_packages,
		},
		pick=('audio_config', 'audio'),
		site='application_handler.install_applications',
	),
	Section(
		'media_codecs',
		lambda: MediaCodecsApp().packages,
		pick=('media_codecs_config', 'enabled'),
		site='application_handler.install_applications',
	),
	Section(
		'flatpak',
		lambda: FlatpakApp().packages,
		pick=('flatpak_config', 'enabled'),
		site='application_handler.install_applications',
	),
	Section(
		'power_management',
		lambda: {
			PowerManagement.PPD.value: PowerManagementApp().ppd_packages,
			PowerManagement.TUNED.value: PowerManagementApp().tuned_packages,
		},
		pick=('power_management_config', 'power_management'),
		site='application_handler.install_applications',
	),
	Section(
		'cpu_scheduler',
		lambda: CPUSchedulerApp().packages,
		pick=('cpu_scheduler_config', 'scheduler'),
		site='application_handler.install_applications',
	),
	Section(
		'printing',
		lambda: PrintServiceApp().packages,
		pick=('print_service_config', 'enabled'),
		site='application_handler.install_applications',
	),
	Section(
		'firewalls',
		lambda: {
			Firewall.UFW.value: FirewallApp().ufw_packages,
			Firewall.FWD.value: FirewallApp().fwd_packages,
		},
		pick=('firewall_config', 'firewall'),
		site='application_handler.install_applications',
	),
	Section('management', lambda: _one_to_one(Management), pick=('management_config', 'tools'), site='application_handler.install_applications'),
	Section('monitors', lambda: _one_to_one(Monitor), pick=('monitor_config', 'monitor'), site='application_handler.install_applications'),
	Section(
		'editors',
		lambda: {e.value: e.packages for e in Editor},
		pick=('editor_config', 'editor'),
		site='application_handler.install_applications',
	),
	Section(
		'terminals',
		lambda: {t.value: t.packages for t in Terminal},
		pick=('terminal_config', 'terminal'),
		site='application_handler.install_applications',
	),
	Section(
		'security',
		lambda: {
			Security.APPARMOR.value: SecurityApp().apparmor_packages,
			Security.FIREJAIL.value: SecurityApp().firejail_packages,
			Security.BUBBLEWRAP.value: SecurityApp().bubblewrap_packages,
			**{s.value: [s.value] for s in Security if s not in (Security.APPARMOR, Security.FIREJAIL, Security.BUBBLEWRAP)},
		},
		pick=('security_config', 'tools'),
		site='application_handler.install_applications',
	),
	Section(
		'languages',
		lambda: _one_to_one(Language),
		pick=('development_config', 'language_config', 'tools'),
		site='application_handler.install_applications',
	),
	Section(
		'devtools',
		lambda: _one_to_one(DevTool),
		pick=('development_config', 'devtool_config', 'tools'),
		site='application_handler.install_applications',
	),
	Section('snapshots', lambda: {s.value: s.packages for s in SnapshotType}, site='installation.setup_btrfs_snapshot'),
	Section('grub_extra', lambda: snapshots.__grub_snapshot_packages__, site='installation.setup_btrfs_snapshot'),
	Section(
		'bootloaders',
		lambda: {b.value: b.packages() for b in Bootloader},
		site='installation.add_bootloader',
	),
	Section(
		'bootloaders_bios',
		lambda: {b.value: b.packages(uefi=False) for b in Bootloader if b.has_bios_support()},
		site='installation.add_bootloader',
	),
	Section(
		'network_iso_extra',
		lambda: ISO_PSK_EXTRA,
		site='network_handler.install_network_config',
	),
	Section(
		'network',
		lambda: {n.value: n.packages for n in NicType},
		site='network_handler.install_network_config',
	),
	Section(
		'network_desktop_extra',
		lambda: NM_DESKTOP_EXTRA,
		site='network_handler.install_network_config',
	),
	Section(
		'gfx_drivers',
		lambda: {d.value: [p.value for p in GFX_PACKAGES[d]] for d in GfxDriver},
		site='profile_handler.install_profile_config',
	),
	Section(
		'gfx_custom_choices',
		lambda: [p.value for p in GFX_CUSTOM_CHOICES],
		site='profile_handler.install_profile_config',
	),
	Section(
		'gfx_drivers_dkms',
		lambda: {d.value: [p.value for p in d.gfx_packages(_DKMS_KERNEL)] for d in GfxDriver if d.has_dkms_variant()},
		site='profile_handler.install_profile_config',
	),
	Section(
		'gfx_mesa_extra',
		lambda: {vendor: [p.value for p in pkgs] for vendor, pkgs in MESA_HOST_EXTRA.items()},
		site='profile_handler.install_profile_config',
	),
	Section(
		'xorg_extra',
		lambda: [p.value for p in XORG_EXTRA],
		site='profile_handler.install_profile_config',
	),
	Section(
		'profile_base',
		lambda: {p.name: p.packages for p in ProfileHandler().profiles if p.profile_type in (ProfileType.Desktop, ProfileType.Server)},
		site='profile_handler.install_profile_config',
	),
	Section(
		'profiles',
		lambda: {p.name: p.packages for p in _leaves()},
		site='profile_handler.install_profile_config',
	),
	Section(
		'compositors',
		lambda: {p.name: p.compositor_packages for p in _leaves() if p.compositor_packages},
		site='profile_handler.install_profile_config',
	),
	Section(
		'seat_access',
		lambda: {s.name: [s.value] for s in SeatAccess},
		site='profile_handler.install_profile_config',
	),
	Section(
		'greeters',
		lambda: {g.value: g.packages for g in GreeterType},
		site='profile_handler.install_profile_config',
	),
	Section(
		'aur_bootstrap',
		lambda: aur.__aur_bootstrap_packages__,
		site='run_grimoire_installation',
	),
)


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
# `packages`.
#
# To change what a section holds, change the code under the banner above it, then:
#
#     python -m archinstoo --script schema
"""


def _key(name: str) -> str:
	# TOML bare keys allow letters, digits, - and _; anything else gets quoted
	ok = name and all(c.isalnum() or c in '-_' for c in name)
	return name if ok else json.dumps(name)


def _list(values: list[str]) -> str:
	return '[' + ', '.join(json.dumps(v) for v in values) + ']'


def _tables(section: Section) -> list[tuple[str, Table]]:
	# (header, table) pairs. a flat list becomes one table under `packages`; a
	# nested value (compositors) becomes one [section.name] table per profile
	value = section.value()
	if isinstance(value, list):
		return [(_key(section.key), {'packages': value})]

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
	# every call in perform_installation, in source order, as the callee is
	# written: `installation.setup_swap`, `ShellApp().install`, `Installer`
	def __init__(self) -> None:
		self.order: list[str] = []

	@override
	def visit_Call(self, node: ast.Call) -> None:
		name = ast.unparse(node.func)
		if name not in self.order:
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
		for header, table in _tables(section):
			lines.append(f'[{header}]')
			lines += [f'{_key(name)} = {_list(pkgs)}' for name, pkgs in table.items()]
			lines.append('')

	return '\n'.join(lines)


def write(path: Path = SCHEMA_PATH) -> None:
	path.write_text(render())
