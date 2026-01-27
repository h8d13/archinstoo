"""Count packages that would be installed from a saved config.

Resolves full dependency tree via pactree (pacman-contrib).
Usage: archinstall --script count path/to/user_configuration.json
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

from archinstall.lib.general import SysCommand
from archinstall.lib.utils.env import Os

Os.locate_binary('pactree')

_schema_path = Path(__file__).parents[2] / 'schema.jsonc'


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
	bl = config.get('bootloader_config', {})
	bl_name = bl.get('bootloader', '')
	if bl_name in SCHEMA['bootloaders']:
		pkgs.update(SCHEMA['bootloaders'][bl_name])

	# user packages
	for p in config.get('packages', []):
		if p:
			pkgs.add(p)

	# profile
	pc = config.get('profile_config', {})
	profile = pc.get('profile', {})
	main = profile.get('main', '')
	details = profile.get('details', [])
	custom_settings = profile.get('custom_settings', {})
	profiles = SCHEMA['profiles']

	if main == 'Desktop':
		pkgs.update(SCHEMA['desktop_base'])

	for name in details:
		if name in profiles:
			pkgs.update(profiles[name])

		# seat_access for sway/river/niri/labwc
		settings = custom_settings.get(name, {})
		if seat := settings.get('seat_access'):
			pkgs.add(seat)

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
		if gfx == 'Nvidia (open kernel module for newer GPUs, Turing+)':
			if any('-' in k for k in kernels):
				pkgs.discard('nvidia-open')
				pkgs.add('nvidia-open-dkms')
				pkgs.add('dkms')
				pkgs.update(f'{k}-headers' for k in kernels)

	# network
	net = config.get('network_config', {})
	net_type = net.get('type', '')
	if net_type in SCHEMA['network']:
		pkgs.update(SCHEMA['network'][net_type])
		if main == 'Desktop':
			pkgs.update(SCHEMA['network']['nm_desktop_extra'])

	# privilege escalation
	auth = config.get('auth_config', {})
	priv_esc = auth.get('privilege_escalation', 'sudo')
	if priv_esc in SCHEMA['privilege_escalation']:
		pkgs.update(SCHEMA['privilege_escalation'][priv_esc])

	# applications
	app = config.get('app_config', {})

	if app.get('bluetooth_config', {}).get('enabled', False):
		pkgs.update(SCHEMA['bluetooth'])

	audio = app.get('audio_config', {}).get('audio', '')
	if audio in SCHEMA['audio']:
		pkgs.update(SCHEMA['audio'][audio])

	pm = app.get('power_management_config', {}).get('power_management', '')
	if pm in SCHEMA['power_management']:
		pkgs.update(SCHEMA['power_management'][pm])

	if app.get('print_service_config', {}).get('enabled', False):
		pkgs.update(SCHEMA['printing'])

	fw = app.get('firewall_config', {}).get('firewall', '')
	if fw in SCHEMA['firewalls']:
		pkgs.update(SCHEMA['firewalls'][fw])

	for tool in app.get('management_config', {}).get('tools', []):
		if tool in SCHEMA['management']:
			pkgs.update(SCHEMA['management'][tool])

	monitor = app.get('monitor_config', {}).get('monitor', '')
	if monitor in SCHEMA['monitors']:
		pkgs.update(SCHEMA['monitors'][monitor])

	editor = app.get('editor_config', {}).get('editor', '')
	if editor in SCHEMA['editors']:
		pkgs.update(SCHEMA['editors'][editor])

	shell = app.get('shell_config', {}).get('shell', '')
	if shell in SCHEMA['shells']:
		pkgs.update(SCHEMA['shells'][shell])

	# filesystem tools
	disk = config.get('disk_config', {})
	fs_tools = SCHEMA['filesystem_tools']
	for dev in disk.get('device_modifications', []):
		for part in dev.get('partitions', []):
			if (fs := part.get('fs_type', '')) in fs_tools:
				pkgs.update(fs_tools[fs])
		for vol in dev.get('lvm_config', {}).get('volumes', []):
			if (fs := vol.get('fs_type', '')) in fs_tools:
				pkgs.update(fs_tools[fs])

	# snapshots
	btrfs = disk.get('btrfs_options', {})
	snapshot = btrfs.get('snapshot_config', {})
	snap_type = snapshot.get('type', '')
	if snap_type in SCHEMA['snapshots']:
		pkgs.update(SCHEMA['snapshots'][snap_type])
		# grub + btrfs snapshots
		if bl_name == 'Grub':
			pkgs.update(SCHEMA['grub_btrfs'])

	# swap
	swap = config.get('swap', {})
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
		name = name.split(sep)[0]
	return name or None


def resolve_deps(explicit: set[str]) -> set[str]:
	"""Resolve the full dependency tree via pactree -sul (sync, unique, linear)."""
	resolved: set[str] = set()

	pkgs = sorted(explicit)
	total = len(pkgs)

	for i, pkg in enumerate(pkgs, 1):
		try:
			output = SysCommand(f'pactree -sul {pkg}')
			for line in output:
				raw = line.decode().strip()
				if name := _clean_dep(raw):
					resolved.add(name)
		except Exception:
			resolved.add(pkg)
		print(f'\r  {i}/{total} | resolved: {len(resolved)}', end='', flush=True)

	print()
	return resolved


def count() -> None:
	parser = argparse.ArgumentParser(description='Count packages from a saved config (resolves deps)')
	parser.add_argument('config', type=str, help='Path to user_configuration.json')

	args = parser.parse_args()

	with open(args.config) as f:
		config = json.load(f)

	explicit = collect(config)

	print(f'\nExplicit packages: {len(explicit)}')
	print('Resolving dependencies...')

	resolved = resolve_deps(explicit)

	print(f'\nTotal packages (with deps): {len(resolved)}')


count()
