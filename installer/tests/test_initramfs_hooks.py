from pathlib import Path

from archinstoo.lib.installer import Installer
from archinstoo.lib.kernel.initramfs import LVM, Initramfs
from archinstoo.lib.models.device import FilesystemType


def _order(hooks: list[str], *names: str) -> list[int]:
	return [hooks.index(n) for n in names]


def test_encrypt_lands_between_block_and_filesystems() -> None:
	initramfs = Initramfs()
	initramfs.add_encrypt()
	initramfs.add_encrypt()  # second layout pass must not stack the hook

	assert initramfs.hooks.count('sd-encrypt') == 1
	assert _order(initramfs.hooks, 'block', 'sd-encrypt', 'filesystems') == sorted(_order(initramfs.hooks, 'block', 'sd-encrypt', 'filesystems'))


def test_bcachefs_hook_follows_block_and_ships_the_module() -> None:
	initramfs = Initramfs()
	initramfs.add_bcachefs()
	initramfs.add_bcachefs()

	assert initramfs.modules == ['bcachefs']
	assert initramfs.hooks.index('bcachefs') == initramfs.hooks.index('block') + 1
	assert initramfs.hooks.count('bcachefs') == 1


def _session(tmp_path: Path) -> Installer:
	installation = Installer.__new__(Installer)
	installation.target = tmp_path
	installation.kernels = ['linux']
	installation.initramfs = Initramfs()
	installation._base_packages = []
	installation._disable_fstrim = False
	return installation


def test_ntfs3_root_drops_fsck(tmp_path: Path) -> None:
	# partitions carry their mountpoint relative to the installed system,
	# so root is / and never the install target path
	installation = _session(tmp_path)
	installation._prepare_fs_type(FilesystemType.NTFS, Path('/'))

	assert 'fsck' not in installation.initramfs.hooks


def test_ntfs3_data_partition_keeps_fsck(tmp_path: Path) -> None:
	installation = _session(tmp_path)
	installation._prepare_fs_type(FilesystemType.NTFS, Path('/data'))

	assert 'fsck' in installation.initramfs.hooks


def test_lvm_hook_sits_between_block_and_filesystems() -> None:
	# https://wiki.archlinux.org/title/Dm-crypt/Encrypting_an_entire_system#Configuring_mkinitcpio_3
	# block sd-encrypt lvm2 filesystems: the volume group needs its
	# device online before lvm2 can activate it
	initramfs = Initramfs()
	initramfs.add_lvm()
	initramfs.add_encrypt(before=LVM)

	assert initramfs.hooks.index('block') < initramfs.hooks.index('sd-encrypt')
	assert initramfs.hooks.index('sd-encrypt') < initramfs.hooks.index(LVM)
	assert initramfs.hooks.index(LVM) < initramfs.hooks.index('filesystems')
