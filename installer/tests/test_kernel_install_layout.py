# kernel-install's layout decides where the kernels and entries land, and
# each loader reads a different place

from pathlib import Path
from types import SimpleNamespace

import pytest

from archinstoo.lib.bootloader.install import BootloaderInstaller
from archinstoo.lib.models.bootloader import Bootloader


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


@pytest.mark.parametrize(('removable', 'variables'), [(True, '--variables=no'), (False, '--variables=yes')])
def test_systemd_boot_removable_leaves_nvram_alone(tmp_path: Path, removable: bool, variables: str) -> None:
	# from an installed host, a registered entry (same title) replaces the
	# host's own and goes first in BootOrder
	calls: list[list[str]] = []
	installer = BootloaderInstaller.__new__(BootloaderInstaller)
	installer.target = tmp_path
	installer.dnf = SimpleNamespace(strap=lambda pkgs: None)  # type: ignore[assignment]
	installer._inst = SimpleNamespace(arch_chroot=calls.append)  # type: ignore[assignment]
	esp = SimpleNamespace(mountpoint=Path('/boot'), relative_mountpoint=Path('boot'))

	installer._add_systemd_bootloader(esp, esp, uki_enabled=False, removable=removable)  # type: ignore[arg-type]

	assert calls == [['bootctl', variables, 'install']]


@pytest.mark.parametrize('path', ['EFI/Linux/fedora.efi', 'EFI/BOOT/BOOTX64.EFI'])
def test_efistub_plugin_keeps_one_file_current(tmp_path: Path, path: str) -> None:
	# the firmware entry (or the fallback path) names one file across kernel
	# updates: the plugin copies each new UKI over it, on add only
	installer = BootloaderInstaller.__new__(BootloaderInstaller)
	installer.target = tmp_path
	installer._write_efistub_plugin(path)

	plugin = tmp_path / 'etc/kernel/install.d/95-fedinstoo-efistub.install'
	script = plugin.read_text()
	assert plugin.stat().st_mode & 0o111
	assert '[ "$1" = add ] || exit 0' in script
	assert f'cp "$KERNEL_INSTALL_STAGING_AREA/uki.efi" "$KERNEL_INSTALL_BOOT_ROOT/{path}"' in script
