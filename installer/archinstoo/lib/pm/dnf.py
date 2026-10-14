import sys
from functools import cache
from pathlib import Path

from archinstoo.lib.chroot import mount_api
from archinstoo.lib.exceptions import RequirementError, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.models.dnf import DnfConfiguration
from archinstoo.lib.output import info, logger
from archinstoo.lib.utils.env import Os

# SysCommand runs under a pty, so dnf draws progress bars even unattended:
# redraw lines per package in a --silent log. argv peek at import, the same
# way --offline is read before argparse runs
_QUIET = ['--quiet'] if '--silent' in sys.argv else []


@cache
def releasever() -> str:
	# the target is the release we run from: the BOOT root, or a Fedora host
	if not (version := Os.os_release('VERSION_ID')):
		raise RequirementError('No VERSION_ID in os-release, cannot pick a Fedora release')
	return version


class Dnf:
	def __init__(self, target: Path, config: DnfConfiguration | None = None) -> None:
		self.target = target
		self.config = config or DnfConfiguration()

	@staticmethod
	def run(args: list[str], peek_output: bool = False) -> SysCommand:
		return SysCommand(['dnf', *args], peek_output=peek_output)

	def _root_args(self) -> list[str]:
		if self.target == Path('/'):
			return []
		# the host's repos and keys resolve the target's packages (the BOOT
		# root or Fedora host is the same release); the target gets its own repo files
		# from fedora-repos, which @core pulls in. tsflags reset: the BOOT
		# root is a container image, whose nodocs would strip man pages
		# https://dnf5.readthedocs.io/en/latest/misc/installroot.7.html#description
		return [
			'--installroot', str(self.target), '--use-host-config',
			f'--releasever={releasever()}', '--setopt=tsflags=',
		]  # fmt: skip

	def strap(self, packages: str | list[str], *, mandatory_groups: bool = False, weak_deps: bool | None = None) -> None:
		if isinstance(packages, str):
			packages = [packages]

		info(f'Installing packages: {packages}')
		# scriptlets run chrooted in the target: kernel-install and dracut
		# need proc, sys and dev there, like the chroot steps after
		mount_api(self.target)
		cmd = ['install', '-y', *_QUIET, *self._root_args()]
		cmd += [f'--setopt={key}={value}' for key, value in self.config.options().items()]
		if mandatory_groups:
			# a group's default tier makes choices (NetworkManager, firewalld,
			# zram) that the install's own steps make instead
			# https://dnf5.readthedocs.io/en/latest/dnf5.conf.5.html#group-package-types-options-label
			# anaconda's kickstart form: @group/mandatory
			# anaconda/pyanaconda/modules/payloads/payload/dnf/utils.py:156-169
			cmd.append('--setopt=group_package_types=mandatory')
		if weak_deps is not None:
			# after the config's own setopt, so this one wins
			cmd.append(f'--setopt=install_weak_deps={weak_deps}')
		cmd += packages
		try:
			self.run(cmd, peek_output=True)
		except SysCallError as err:
			raise RequirementError(f'Package installation failed. See {logger.path} or above message for error details: {err}') from err

	def write_conf(self) -> None:
		# the installed system keeps resolving the way its install did; keys
		# already in [main] are rewritten in place, the rest appended to it
		conf = self.target / 'etc/dnf/dnf.conf'
		lines = conf.read_text().splitlines() if conf.exists() else ['[main]']
		pending = dict(self.config.options())
		kept = []
		for line in lines:
			key = line.split('=', 1)[0].strip()
			kept.append(f'{key}={pending.pop(key)}' if key in pending else line)
		main = next((i for i, line in enumerate(kept) if line.strip() == '[main]'), None)
		if main is None:
			kept[:0] = ['[main]']
			main = 0
		kept[main + 1 : main + 1] = [f'{k}={v}' for k, v in pending.items()]
		conf.parent.mkdir(parents=True, exist_ok=True)
		conf.write_text('\n'.join(kept) + '\n')
		info(f'Wrote {", ".join(self.config.options())} to {conf}')
