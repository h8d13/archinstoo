"""Count packages that would be installed from a saved config.

Resolves full dependency tree via pactree (pacman-contrib).
Usage: archinstoo --script count path/to/user_configuration.json
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

from archinstoo.lib.general import SysCommand
from archinstoo.lib.utils.env import Os

Os.locate_binary('pactree')

_schema_path = Path(__file__).parent.parent / 'schema.jsonc'


def _load_schema() -> dict[str, Any]:
	"""Load schema.jsonc, stripping // comments."""
	text = _schema_path.read_text()
	text = re.sub(r'(?m)^\s*//.*$|(?<=,)\s*//.*$', '', text)
	result: dict[str, Any] = json.loads(text)
	return result


SCHEMA = _load_schema()


def collect(config: dict[str, Any]) -> set[str]:
	pkgs: set[str] = set()

	# base
	pkgs.update(SCHEMA['base'])

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
			pkgs.update(SCHEMA['profile_base'])

		tp_details = tp.get('details', []) or []
		details.extend(tp_details)
		custom_settings = tp.get('custom_settings') or {}

		for name in tp_details:
			settings = custom_settings.get(name) or {}
			excluded = set(settings.get('excluded_packages') or [])

			if name in profiles:
				pkgs.update(p for p in profiles[name] if p not in excluded)

			# seat_access for sway/river/niri/labwc
			if (seat := settings.get('seat_access')) and seat not in excluded:
				pkgs.add(seat)

	main = next(iter(mains), '')

	# greeter
	greeter = pc.get('greeter', '')
	if greeter in SCHEMA['greeters']:
		pkgs.update(SCHEMA['greeters'][greeter])

	# gfx driver
	gfx = pc.get('gfx_driver', '')
	if gfx in SCHEMA['gfx_drivers']:
		pkgs.update(SCHEMA['gfx_drivers'][gfx])
		xorg_profiles = set(SCHEMA['xorg_profiles'])
		if any(d in xorg_profiles for d in details):
			pkgs.update(['xorg-server', 'xorg-xinit'])
		# dkms for nvidia with non-standard kernels
		if gfx == 'Nvidia (open kernel module for newer GPUs, Turing+)' and any('-' in k for k in kernels):
			pkgs.discard('nvidia-open')
			pkgs.add('nvidia-open-dkms')
			pkgs.add('dkms')
			pkgs.update(f'{k}-headers' for k in kernels)

	# network
	net = config.get('network_config') or {}
	net_type = net.get('type', '')
	if net_type in SCHEMA['network']:
		pkgs.update(SCHEMA['network'][net_type])
		if 'Desktop' in mains and net_type in ('nm', 'nm_iwd'):
			pkgs.update(SCHEMA['network']['nm_desktop_extra'])

	# privilege escalation
	auth = config.get('auth_config') or {}
	priv_esc = auth.get('privilege_escalation', 'sudo')
	if priv_esc in SCHEMA['privilege_escalation']:
		pkgs.update(SCHEMA['privilege_escalation'][priv_esc])

	# applications
	app = config.get('app_config') or {}

	if (app.get('bluetooth_config') or {}).get('enabled', False):
		pkgs.update(SCHEMA['bluetooth'])

	audio = (app.get('audio_config') or {}).get('audio', '')
	if audio in SCHEMA['audio']:
		pkgs.update(SCHEMA['audio'][audio])

	pm = (app.get('power_management_config') or {}).get('power_management', '')
	if pm in SCHEMA['power_management']:
		pkgs.update(SCHEMA['power_management'][pm])

	if (app.get('print_service_config') or {}).get('enabled', False):
		pkgs.update(SCHEMA['printing'])

	fw = (app.get('firewall_config') or {}).get('firewall', '')
	if fw in SCHEMA['firewalls']:
		pkgs.update(SCHEMA['firewalls'][fw])

	for tool in (app.get('management_config') or {}).get('tools', []) or []:
		if tool in SCHEMA['management']:
			pkgs.update(SCHEMA['management'][tool])

	for tool in (app.get('security_config') or {}).get('tools', []) or []:
		if tool in SCHEMA['security']:
			pkgs.update(SCHEMA['security'][tool])

	monitor = (app.get('monitor_config') or {}).get('monitor', '')
	if monitor in SCHEMA['monitors']:
		pkgs.update(SCHEMA['monitors'][monitor])

	editor = (app.get('editor_config') or {}).get('editor', '')
	if editor in SCHEMA['editors']:
		pkgs.update(SCHEMA['editors'][editor])

	# shells (per-user in auth_config)
	for user in auth.get('users', []) or []:
		shell = user.get('shell', '')
		if shell in SCHEMA['shells']:
			pkgs.update(SCHEMA['shells'][shell])

	# filesystem tools
	disk = config.get('disk_config') or {}
	fs_tools = SCHEMA['filesystem_tools']
	for dev in disk.get('device_modifications', []) or []:
		for part in dev.get('partitions', []) or []:
			if (fs := part.get('fs_type', '')) in fs_tools:
				pkgs.update(fs_tools[fs])
		for vol in (dev.get('lvm_config') or {}).get('volumes', []) or []:
			if (fs := vol.get('fs_type', '')) in fs_tools:
				pkgs.update(fs_tools[fs])

	# snapshots
	btrfs = disk.get('btrfs_options') or {}
	snapshot = btrfs.get('snapshot_config') or {}
	snap_type = snapshot.get('type', '')
	if snap_type in SCHEMA['snapshots']:
		pkgs.update(SCHEMA['snapshots'][snap_type])
		# grub + btrfs snapshots
		if bl_name == 'Grub':
			pkgs.update(SCHEMA['grub_btrfs'])

	# swap
	swap = config.get('swap') or {}
	if swap.get('enabled', False):
		pkgs.update(SCHEMA['swap'].get('zram', []))

	print(pkgs)
	return pkgs


def _clean_dep(name: str) -> str | None:
	"""Strip version constraints and filter out .so provides."""
	if '.so' in name:
		return None
	# strip >=, <=, =, >, <
	for sep in ('>=', '<=', '=', '>', '<'):
		name = name.split(sep, 1)[0]
	return name or None


_TREE_PREFIX_RE = re.compile(r'^[\s│├└─]*')


def resolve_deps(explicit: set[str], target: str | None = None) -> tuple[set[str], list[str]]:
	"""Resolve the full dependency tree via `pactree -s`.

	`-s` keeps tree formatting and emits "<pkg> provides <virtual>" so we can
	recover the real package name when a dep is satisfied by a .so virtual.
	`-u` (unique) is omitted because it sometimes collapses such lines to the
	bare virtual, hiding the providing package (e.g. networkmanager →
	wpa_supplicant → pcsclite → polkit gets shown as just libpolkit-gobject-1.so).

	If `target` is given, also return explicit packages whose closure contains it.
	"""
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


def count() -> None:
	parser = argparse.ArgumentParser(
		prog='python -m archinstoo --script count',
		description='Count packages from a saved config (resolves deps)',
	)
	parser.add_argument('config', type=str, help='Path to user_configuration.json')
	parser.add_argument('--why', metavar='PKG', help='Show which explicit packages pull in PKG and the dep chain')

	args = parser.parse_args()

	with open(args.config) as f:
		config = json.load(f)

	explicit = collect(config)

	print(f'\nExplicit packages: {len(explicit)}')
	print('Resolving dependencies...')

	resolved, roots = resolve_deps(explicit, target=args.why)

	print(f'\nTotal packages (with deps): {len(resolved)}')

	if args.why:
		if not roots:
			print(f"\n'{args.why}' is not pulled in by this config.")
		else:
			print(f"\n'{args.why}' is pulled in by {len(roots)} explicit package(s):")
			for root in sorted(roots):
				print(f'  {root}')


count()
