import os
import re
from subprocess import CompletedProcess
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import DiskError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.output import info

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


# No resume hook (the systemd initramfs hook ships it) and no kernel
# params on UEFI (systemd-sleep records the HibernateLocation EFI var);
# only BIOS needs resume=/resume_offset=.
def setup_swapfile(installation: Installer, size_gib: int) -> tuple[str, list[str]]:
	# ceil MemTotal (kB) to GiB: the image must fit even on a full RAM
	size = size_gib or -(-SysInfo.mem_total() // 2**20)
	fs_type = SysCommand(['findmnt', '-no', 'FSTYPE', str(installation.target)]).decode().strip()
	if fs_type == 'bcachefs':
		# mkswap --file succeeds but swapon returns EINVAL: the kernel
		# side has no swap file support. zram still covers swap
		raise DiskError('bcachefs cannot host a swap file, hibernation skipped')
	info(f'Setting up {size}GiB swap file on {fs_type}')

	if fs_type == 'btrfs':
		# nested subvolume: snapshots of the parent don't recurse into
		# it, so root snapshots keep working with the swapfile in place
		swapfile = '/swap/swapfile'
		installation.arch_chroot(['btrfs', 'subvolume', 'create', '/swap'])
		installation.arch_chroot(['btrfs', 'filesystem', 'mkswapfile', '--size', f'{size}g', '--uuid', 'clear', swapfile])
	else:
		swapfile = '/swapfile'
		installation.arch_chroot(['mkswap', '-U', 'clear', '--size', f'{size}G', '--file', swapfile])

	fstab_entry = f'{swapfile}\tnone\tswap\tdefaults\t0\t0'
	kernel_params: list[str] = []

	if not SysInfo.has_uefi():
		fs_uuid = SysCommand(['findmnt', '-no', 'UUID', str(installation.target)]).decode().strip()
		if fs_type == 'btrfs':
			result = installation.arch_chroot(['btrfs', 'inspect-internal', 'map-swapfile', '-r', swapfile])
			offset = result.stdout.decode().strip() if isinstance(result, CompletedProcess) else str(result).strip()
		else:
			# the kernel wants the offset in PAGE_SIZE units, filefrag's
			# default unit is the fs block size; page size is an arch
			# property (arm64 kernels ship 4k/16k/64k), not always 4096
			page_size = os.sysconf('SC_PAGE_SIZE')
			result = installation.arch_chroot(['filefrag', f'-b{page_size}', '-v', swapfile])
			out = result.stdout.decode() if isinstance(result, CompletedProcess) else str(result)
			match = re.search(r'^\s*0:\s+\d+\.\.\s*\d+:\s+(\d+)', out, re.MULTILINE)
			if not match:
				raise DiskError(f'Could not determine swap file offset from filefrag:\n{out}')
			offset = match.group(1)
		kernel_params = [f'resume=UUID={fs_uuid}', f'resume_offset={offset}']
	return fstab_entry, kernel_params
