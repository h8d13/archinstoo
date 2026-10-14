# setfiles stays on the filesystem it starts in: every directory where the
# device changes (btrfs subvolume, mount) has to be handed to it as a root

import os
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib import selinux

if TYPE_CHECKING:
	from collections.abc import Callable

	import pytest


def test_device_changes_are_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	for d in ('home/vm', 'swap', 'proc/1', 'boot/efi', 'usr/bin', 'run'):
		(tmp_path / d).mkdir(parents=True)
	# /var/run -> /run: os.walk lists it with the dirs, stat() would follow it
	(tmp_path / 'var').mkdir()
	(tmp_path / 'var/run').symlink_to('../run')
	# home and swap sit on their own devices; proc and the ESP are excluded
	devices = {tmp_path / 'home': 2, tmp_path / 'home/vm': 2, tmp_path / 'swap': 3, tmp_path / 'proc': 4, tmp_path / 'boot/efi': 5, tmp_path / 'run': 6}
	real_stat = Path.stat

	def fake(follow: bool) -> Callable[..., os.stat_result]:
		def stat(self: Path, **kw: object) -> os.stat_result:
			st = real_stat(self, follow_symlinks=follow)
			dev = devices.get(self.resolve() if follow else self, 1)
			return os.stat_result((st.st_mode, st.st_ino, dev, *tuple(st)[3:]))

		return stat

	monkeypatch.setattr(Path, 'stat', fake(follow=True))
	monkeypatch.setattr(Path, 'lstat', fake(follow=False))

	assert sorted(selinux._fs_roots(tmp_path, ['/proc', '/boot/efi', '/run'])) == ['/', '/home', '/swap']
