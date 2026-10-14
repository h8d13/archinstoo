# kernel-install's layout decides where the kernels and entries land, and
# each loader reads a different place

from typing import TYPE_CHECKING

import pytest

from archinstoo.lib.bootloader.install import BootloaderInstaller
from archinstoo.lib.models.bootloader import Bootloader

if TYPE_CHECKING:
	from pathlib import Path


@pytest.mark.parametrize(
	('bootloader', 'uki', 'expected'),
	[
		# 'bls' makes kernel-install create $BOOT/<id>/<ver>, which
		# 20-grub.install reads as another loader and bows out
		(Bootloader.Grub, False, ['layout=other']),
		(Bootloader.Systemd, False, ['layout=bls']),
		(Bootloader.Systemd, True, ['layout=uki', 'uki_generator=ukify']),
	],
)
def test_layout_follows_the_loader(tmp_path: Path, bootloader: Bootloader, uki: bool, expected: list[str]) -> None:
	installer = BootloaderInstaller.__new__(BootloaderInstaller)
	installer.target = tmp_path
	installer._write_install_conf(bootloader, uki)

	lines = (tmp_path / 'etc/kernel/install.conf').read_text().splitlines()
	assert lines == [*expected, 'initrd_generator=dracut']


def test_grub_cmdline_carries_the_params(tmp_path: Path) -> None:
	# grub2-mkconfig rebuilds every BLS entry's options from this line plus
	# its own root=UUID=... ro: anything left out never reaches the kernel
	installer = BootloaderInstaller.__new__(BootloaderInstaller)
	installer.target = tmp_path
	installer._write_grub_default(['rd.luks.name=abc=root', 'root=/dev/mapper/root', 'rootflags=subvol=@', 'rw', 'rootfstype=ext4', 'console=ttyS0,115200'])

	grub = (tmp_path / 'etc/default/grub').read_text()
	assert 'GRUB_CMDLINE_LINUX="rd.luks.name=abc=root rootfstype=ext4 console=ttyS0,115200"\n' in grub
	assert 'GRUB_ENABLE_BLSCFG=true\n' in grub
