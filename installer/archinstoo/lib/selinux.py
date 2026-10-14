import json
import re
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.output import debug, info, warn

if TYPE_CHECKING:
	from pathlib import Path

	from archinstoo.lib.installer import Installer

# rpm only sets file contexts when the host itself runs SELinux. From BOOT
# (any host) every file lands unlabeled, and enforcing then denies PID1
# before .autorelabel's own service could run. So the tree is labeled at
# install time with the target's setfiles and policy, as image builders do

CONFIG = 'etc/selinux/config'
_API_DIRS = ('/proc', '/sys', '/dev', '/run', '/tmp')  # noqa: S108 - the target's own tmpfs, excluded
# no xattrs to hold a context: labeled by mount option, not by setfiles
_NO_XATTR = ('vfat', 'exfat')


def _policy(target: Path) -> str | None:
	config = target / CONFIG
	if not config.exists():
		return None
	if m := re.search(r'^SELINUXTYPE=(\S+)', config.read_text(), re.MULTILINE):
		return m.group(1)
	return None


def _no_xattr_mounts(target: Path) -> list[str]:
	out = SysCommand(['findmnt', '-J', '-R', '-o', 'TARGET,FSTYPE', str(target)]).decode()
	stack = json.loads(out)['filesystems']
	found = []
	while stack:
		fs = stack.pop()
		stack.extend(fs.get('children', []))
		if fs['fstype'] in _NO_XATTR:
			found.append('/' + fs['target'].removeprefix(str(target)).lstrip('/'))
	return found


def _fallback_permissive(target: Path) -> None:
	# boots unconfined, relabels on the way up; enforcing is one edit away
	# https://docs.fedoraproject.org/en-US/quick-docs/selinux-changing-states-and-modes/#_changing_to_enforcing_mode
	config = target / CONFIG
	config.write_text(re.sub(r'^SELINUX=\S+', 'SELINUX=permissive', config.read_text(), flags=re.MULTILINE))
	(target / '.autorelabel').touch()
	warn(f'SELinux left permissive with a relabel queued; set SELINUX=enforcing in /{CONFIG} after the first boot')


def label_target(installation: Installer) -> None:
	target = installation.target
	if (policy := _policy(target)) is None:
		debug('No SELinux policy on the target, nothing to label')
		return

	contexts = f'/etc/selinux/{policy}/contexts/files/file_contexts'
	excludes = [*_API_DIRS, *_no_xattr_mounts(target)]
	info(f'Labeling the target for SELinux ({policy})', step=True)
	try:
		installation.arch_chroot(['setfiles', '-F', '-T0', *(f'-e{d}' for d in excludes), contexts, '/'])
	except SysCallError as err:
		warn(f'setfiles failed: {err}')
		_fallback_permissive(target)
