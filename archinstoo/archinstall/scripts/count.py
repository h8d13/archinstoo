"""Count packages that would be installed from a saved config.

Resolves full dependency tree via pactree (pacman-contrib).
Usage: archinstall --script count path/to/user_configuration.json
"""

import argparse
import json
from typing import Any

from archinstall.lib.general import SysCommand
from archinstall.lib.utils.env import Os

Os.require_binary('pactree')

# map all packages

# -- Base system (always installed) --
BASE_PACKAGES = ['base', 'linux-firmware']

# -- Desktop base (added when profile.main == 'Desktop') --
DESKTOP_BASE = ['vi', 'openssh', 'wget', 'iwd', 'wireless_tools', 'smartmontools', 'xdg-utils']

# -- Profile -> package mapping --
# Keep in sync with default_profiles/desktops/ and default_profiles/servers/
PROFILE_PACKAGES: dict[str, list[str]] = {
	# Desktop environments
	'KDE Plasma': ['plasma-desktop', 'plasma-pa', 'kscreen', 'konsole', 'kate', 'dolphin', 'ark', 'plasma-workspace'],
	'GNOME': ['gnome', 'gnome-tweaks'],
	'Xfce4': ['xfce4', 'xfce4-goodies', 'pavucontrol', 'gvfs', 'xarchiver'],
	'Cinnamon': [
		'cinnamon',
		'system-config-printer',
		'gnome-keyring',
		'gnome-terminal',
		'engrampa',
		'gnome-screenshot',
		'gvfs-smb',
		'xed',
		'xdg-user-dirs-gtk',
	],
	'MATE': ['mate', 'mate-extra'],
	'Budgie': ['materia-gtk-theme', 'budgie', 'mate-terminal', 'nemo', 'papirus-icon-theme'],
	'LXQt': ['lxqt', 'breeze-icons', 'oxygen-icons', 'xdg-utils', 'ttf-freefont', 'l3afpad', 'slock'],
	'Cutefish': ['cutefish', 'noto-fonts'],
	'Deepin': ['deepin', 'deepin-terminal', 'deepin-editor'],
	'Cosmic': ['cosmic', 'xdg-user-dirs'],
	# Wayland WMs
	'Hyprland': [
		'hyprland',
		'dunst',
		'kitty',
		'uwsm',
		'dolphin',
		'wofi',
		'xdg-desktop-portal-hyprland',
		'qt5-wayland',
		'qt6-wayland',
		'polkit-kde-agent',
		'grim',
		'slurp',
	],
	'Sway': ['sway', 'swaybg', 'swaylock', 'swayidle', 'waybar', 'wmenu', 'brightnessctl', 'grim', 'slurp', 'pavucontrol', 'foot', 'xorg-xwayland'],
	'River': ['foot', 'xdg-desktop-portal-wlr', 'river'],
	'Niri': ['niri', 'alacritty', 'fuzzel', 'mako', 'xorg-xwayland', 'waybar', 'swaybg', 'swayidle', 'swaylock', 'xdg-desktop-portal-gnome'],
	'Labwc': ['alacritty', 'labwc'],
	# Xorg WMs
	'i3-wm': ['i3-wm', 'i3lock', 'i3status', 'i3blocks', 'xss-lock', 'xterm', 'lightdm-gtk-greeter', 'lightdm', 'dmenu'],
	'Bspwm': ['bspwm', 'sxhkd', 'dmenu', 'xdo', 'rxvt-unicode'],
	'Awesome': [
		'xorg-server',
		'awesome',
		'alacritty',
		'xorg-xinit',
		'xorg-xrandr',
		'xterm',
		'feh',
		'slock',
		'terminus-font',
		'gnu-free-fonts',
		'ttf-liberation',
		'xsel',
	],
	'Enlightenment': ['enlightenment', 'terminology'],
	'Qtile': ['qtile', 'alacritty'],
	'Xmonad': ['xmonad', 'xmonad-contrib', 'xmonad-extras', 'xterm', 'dmenu'],
	# Servers
	'Nginx': ['nginx'],
	'Docker': ['docker'],
	'httpd': ['apache'],
	'sshd': ['openssh'],
	'PostgreSQL': ['postgresql'],
	'MariaDB': ['mariadb'],
	'Lighttpd': ['lighttpd'],
	'Tomcat': ['tomcat10'],
	'Cockpit': ['cockpit', 'udisks2', 'packagekit'],
}

# -- Greeter -> packages --
GREETER_PACKAGES: dict[str, list[str]] = {
	'lightdm-slick-greeter': ['lightdm', 'lightdm-slick-greeter'],
	'lightdm-gtk-greeter': ['lightdm', 'lightdm-gtk-greeter'],
	'sddm': ['sddm'],
	'gdm': ['gdm'],
	'ly': ['ly'],
	'cosmic-greeter': ['cosmic-greeter'],
}

# -- GFX driver -> packages --
GFX_DRIVER_PACKAGES: dict[str, list[str]] = {
	'All open-source': [
		'mesa',
		'xf86-video-amdgpu',
		'xf86-video-ati',
		'xf86-video-nouveau',
		'libva-mesa-driver',
		'libva-intel-driver',
		'intel-media-driver',
		'vulkan-radeon',
		'vulkan-intel',
		'vulkan-nouveau',
	],
	'AMD / ATI (open-source)': ['mesa', 'xf86-video-amdgpu', 'xf86-video-ati', 'libva-mesa-driver', 'vulkan-radeon'],
	'Intel (open-source)': ['mesa', 'libva-intel-driver', 'intel-media-driver', 'vulkan-intel'],
	'Nvidia (open kernel module for newer GPUs, Turing+)': ['nvidia-open', 'libva-nvidia-driver'],
	'Nvidia (open-source nouveau driver)': ['mesa', 'xf86-video-nouveau', 'vulkan-nouveau'],
	'VirtualBox (open-source)': ['mesa'],
}

# Profiles that use X11 -> gfx driver adds xorg-server/xorg-xinit
XORG_PROFILES = {'Xfce4', 'Cinnamon', 'MATE', 'Budgie', 'LXQt', 'Cutefish', 'Deepin', 'i3-wm', 'Bspwm', 'Awesome', 'Enlightenment', 'Qtile', 'Xmonad'}

PIPEWIRE_PACKAGES = ['pipewire', 'pipewire-alsa', 'pipewire-jack', 'pipewire-pulse', 'gst-plugin-pipewire', 'libpulse', 'wireplumber']
BLUETOOTH_PACKAGES = ['bluez', 'bluez-utils']
PRINT_PACKAGES = ['cups', 'system-config-printer', 'cups-pk-helper']


def collect(config: dict[str, Any]) -> set[str]:
	pkgs: set[str] = set()

	# base
	pkgs.update(BASE_PACKAGES)

	# kernels
	kernels = config.get('kernels', ['linux'])
	pkgs.update(kernels)

	# kernel headers
	if config.get('kernel_headers', False):
		pkgs.update(f'{k}-headers' for k in kernels)

	# bootloader
	bl = config.get('bootloader_config', {})
	if bl.get('bootloader') == 'Grub':
		pkgs.add('grub')

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

	if main == 'Desktop':
		pkgs.update(DESKTOP_BASE)

	for name in details:
		if name in PROFILE_PACKAGES:
			pkgs.update(PROFILE_PACKAGES[name])

		# seat_access for sway/river/niri/labwc
		settings = custom_settings.get(name, {})
		if seat := settings.get('seat_access'):
			pkgs.add(seat)

	# greeter
	greeter = pc.get('greeter', '')
	if greeter in GREETER_PACKAGES:
		pkgs.update(GREETER_PACKAGES[greeter])

	# gfx driver
	gfx = pc.get('gfx_driver', '')
	if gfx in GFX_DRIVER_PACKAGES:
		pkgs.update(GFX_DRIVER_PACKAGES[gfx])
		if any(d in XORG_PROFILES for d in details):
			pkgs.update(['xorg-server', 'xorg-xinit'])
		# dkms for nvidia with non-standard kernels
		if gfx == 'Nvidia (open kernel module for newer GPUs, Turing+)':
			if any('-' in k for k in kernels):
				pkgs.discard('nvidia-open')
				pkgs.add('nvidia-open-dkms')
				pkgs.add('dkms')
				pkgs.update(f'{k}-headers' for k in kernels)

	# applications
	app = config.get('app_config', {})

	if app.get('bluetooth_config', {}).get('enabled', False):
		pkgs.update(BLUETOOTH_PACKAGES)

	audio = app.get('audio_config', {}).get('audio', '')
	if audio == 'pipewire':
		pkgs.update(PIPEWIRE_PACKAGES)
	elif audio == 'pulseaudio':
		pkgs.add('pulseaudio')

	pm = app.get('power_management_config', {}).get('power_management', '')
	if pm:
		pkgs.add(pm)
		if pm == 'tuned':
			pkgs.add('tuned-ppd')

	if app.get('print_service_config', {}).get('enabled', False):
		pkgs.update(PRINT_PACKAGES)

	fw = app.get('firewall_config', {}).get('firewall', '')
	if fw:
		pkgs.add(fw)

	for tool in app.get('management_config', {}).get('tools', []):
		pkgs.add(tool)

	monitor = app.get('monitor_config', {}).get('monitor', '')
	if monitor:
		pkgs.add(monitor)

	editor = app.get('editor_config', {}).get('editor', '')
	if editor:
		pkgs.add(editor)

	shell = app.get('shell_config', {}).get('shell', '')
	if shell and shell != 'bash':
		pkgs.add(shell)

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
		print(f'\r  {i}/{total}', end='', flush=True)
		try:
			output = SysCommand(f'pactree -sul {pkg}')
			for line in output:
				raw = line.decode().strip()
				if name := _clean_dep(raw):
					resolved.add(name)
		except Exception:
			resolved.add(pkg)

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
