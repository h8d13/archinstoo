import os
import platform
import sys
from pathlib import Path

from .env import Env


def is_venv() -> bool:
	return sys.prefix != getattr(sys, 'base_prefix', sys.prefix)


def is_root() -> bool:
	return os.getuid() == 0


def kernel_info() -> str:
	return f'{platform.release()} built {platform.version()}'


class Host:
	@staticmethod
	def running_from_host() -> bool:
		# returns True when not on the ISO
		return not Path('/run/archiso').exists()

	@staticmethod
	def running_from_who() -> str:
		# distro ID from os-release; stdlib parse handles quoting and the
		# /usr/lib/os-release fallback (no systemd needed, plain file read)
		try:
			return platform.freedesktop_os_release().get('ID', '')
		except OSError:
			return ''

	@staticmethod
	def running_from_arch() -> bool:
		# distinguishes an Arch host/ISO from a foreign host (Debian, Alpine, ...)
		# archarm is Arch Linux ARM, native for our purposes
		return Host.running_from_who() in ('arch', 'archarm')

	@staticmethod
	def running_from_foreign() -> bool:
		# installed non-Arch host (not the ISO, not an Arch install)
		return Host.running_from_host() and not Host.running_from_arch()

	@staticmethod
	def running_from_arch_host() -> bool:
		# H2T on an installed Arch: '/' is the user's own system, not a live or
		# throwaway root, so archinstoo must not sync or install into it
		return Host.running_from_host() and Host.running_from_arch() and not Host.running_from_bootstrap()

	@staticmethod
	def running_from_bootstrap() -> bool:
		# distros/BOOT: Arch, but a throwaway root (set through arch-chroot)
		return Env.get_value('A2_BOOTSTRAP') == '1'

	@staticmethod
	def running_in_chroot() -> bool:
		# systemd's own test: PID1 sits on another root
		try:
			return not Path('/proc/1/root').samefile('/')
		except OSError:
			return False

	@staticmethod
	def has_systemd() -> bool:
		# sd_booted(), except chroots: arch-chroot binds the host /run in
		return Path('/run/systemd/system').is_dir() and not Host.running_in_chroot()

	@staticmethod
	def invoking_username() -> str | None:
		# the human behind sudo/doas; None when running as real root (su -, autologin)
		name = Env.get_value('SUDO_USER') or Env.get_value('DOAS_USER')
		if not name or name == 'root':
			return None
		return name
