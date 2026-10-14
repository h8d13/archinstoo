import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.output import debug, info, warn

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer

# rpm only sets file contexts when the host itself runs SELinux. From BOOT
# (any host) every file lands unlabeled, and enforcing then denies PID1
# before .autorelabel's own service could run. So the tree is labeled at
# install time with the target's setfiles and policy, as image builders do.
# anaconda runs on an SELinux host, so it only restorecons a few dirs
# anaconda/pyanaconda/modules/boss/installation.py:271-295

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


def _fs_roots(target: Path, excludes: list[str]) -> list[str]:
	# setfiles stays on the filesystem it starts in, and on btrfs every
	# subvolume is one: mounted (@home) or nested and never mounted (the
	# swapfile's, snapper's .snapshots). A directory whose device differs
	# from its parent's starts one, so each such directory is a root to hand
	# setfiles
	skip = {target / d.lstrip('/') for d in excludes}
	roots = ['/']
	for dirpath, dirnames, _ in os.walk(target):
		parent = Path(dirpath)
		dev = parent.stat().st_dev
		dirnames[:] = [d for d in dirnames if parent / d not in skip]
		# lstat: a symlinked dir (/var/run -> /run) sits on the parent's device
		roots.extend('/' + str((parent / d).relative_to(target)) for d in dirnames if (parent / d).lstat().st_dev != dev)
	return roots


def _fallback_permissive(target: Path) -> None:
	# boots unconfined, relabels on the way up; enforcing is one edit away
	# https://docs.fedoraproject.org/en-US/quick-docs/selinux-changing-states-and-modes/#_changing_to_enforcing_mode
	# anaconda/pyanaconda/modules/security/installation.py:232-240
	config = target / CONFIG
	config.write_text(re.sub(r'^SELINUX=\S+', 'SELINUX=permissive', config.read_text(), flags=re.MULTILINE))
	(target / '.autorelabel').touch()
	warn(f'SELinux left permissive with a relabel queued; set SELINUX=enforcing in /{CONFIG} after the first boot')


def add_file_context(installation: Installer, pattern: str, setype: str) -> None:
	# a local rule in the policy store, for a path the policy has none for;
	# label_target applies it with everything else at the end. semanage
	# lives in policycoreutils-python-utils, outside @core
	if _policy(installation.target) is None:
		return
	installation.add_additional_packages('policycoreutils-python-utils')
	installation.arch_chroot(['semanage', 'fcontext', '-a', '-t', setype, pattern])
	debug(f'SELinux file context {pattern} -> {setype}')


def label_target(installation: Installer) -> None:
	target = installation.target
	if (policy := _policy(target)) is None:
		debug('No SELinux policy on the target, nothing to label')
		return

	contexts = f'/etc/selinux/{policy}/contexts/files/file_contexts'
	excludes = [*_API_DIRS, *_no_xattr_mounts(target)]
	info(f'Labeling the target for SELinux ({policy})', step=True)
	try:
		roots = _fs_roots(target, excludes)
		debug(f'setfiles roots: {roots}')
		installation.arch_chroot(['setfiles', '-F', '-T0', *(f'-e{d}' for d in excludes), contexts, *roots])
	except SysCallError as err:
		warn(f'setfiles failed: {err}')
		_fallback_permissive(target)
