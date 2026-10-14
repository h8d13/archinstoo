import json
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import RequirementError, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.output import debug, info

if TYPE_CHECKING:
	from pathlib import Path

# every block-backed mount under the target, by UUID. The API mounts (proc,
# sys, dev, run) have no UUID and drop out on their own

# options the kernel reports that describe the mount, not a request for it
_RUNTIME_OPTIONS = ('seclabel', 'subvolid=')

# fsck order: root first, then the rest; btrfs/xfs/f2fs check themselves
_FSCK_TYPES = ('ext2', 'ext3', 'ext4', 'vfat')


def fs_uuid(dev_path: Path | str) -> str:
	return SysCommand(['blkid', '-s', 'UUID', '-o', 'value', str(dev_path)]).decode().strip()


def _options(raw: str) -> str:
	return ','.join(o for o in raw.split(',') if not o.startswith(_RUNTIME_OPTIONS))


def _fsck_pass(fstype: str, mountpoint: str) -> int:
	if fstype not in _FSCK_TYPES:
		return 0
	return 1 if mountpoint == '/' else 2


def _mount_entries(target: Path) -> list[str]:
	# -v: source without its [/subvol] suffix, the subvol= option carries it
	out = SysCommand(['findmnt', '-J', '-R', '-v', '-o', 'TARGET,FSTYPE,OPTIONS,UUID', str(target)]).decode()
	stack = json.loads(out)['filesystems']
	entries = []
	while stack:
		fs = stack.pop(0)
		# depth first, parents before children: mount order
		stack[:0] = fs.get('children', [])
		if not fs['uuid']:
			continue
		mountpoint = '/' + fs['target'].removeprefix(str(target)).lstrip('/')
		fstype = fs['fstype']
		entries.append(f'UUID={fs["uuid"]}\t{mountpoint}\t{fstype}\t{_options(fs["options"])}\t0\t{_fsck_pass(fstype, mountpoint)}')
	return entries


def write_fstab(target: Path, extra_entries: list[str]) -> None:
	# the mounts plus what the install learned that findmnt cannot see (swap)
	fstab_path = target / 'etc' / 'fstab'
	info(f'Generating {fstab_path}', step=True)
	try:
		entries = _mount_entries(target)
	except (SysCallError, KeyError, ValueError) as err:
		raise RequirementError(f'Could not generate fstab: {err}') from err
	if not any('\t/\t' in e for e in entries):
		raise RequirementError(f'No root filesystem mounted at {target}')

	lines = [*entries, *extra_entries]
	debug('fstab:\n' + '\n'.join(lines))
	with fstab_path.open('a') as fp:
		fp.writelines(f'{line}\n' for line in lines)
