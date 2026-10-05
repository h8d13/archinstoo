import pytest

from archinstoo.lib import hardware
from archinstoo.lib.kernel.initramfs import LVM, Initramfs


def _order(hooks: list[str], *names: str) -> list[int]:
	return [hooks.index(n) for n in names]


def test_encrypt_lands_between_block_and_filesystems() -> None:
	initramfs = Initramfs()
	initramfs.add_encrypt()
	initramfs.add_encrypt()  # second layout pass must not stack the hook

	assert initramfs.hooks.count('sd-encrypt') == 1
	assert _order(initramfs.hooks, 'block', 'sd-encrypt', 'filesystems') == sorted(_order(initramfs.hooks, 'block', 'sd-encrypt', 'filesystems'))


@pytest.mark.parametrize(('arch', 'present'), [('x86_64', True), ('aarch64', False)])
def test_microcode_hook_only_where_it_applies(monkeypatch: pytest.MonkeyPatch, arch: str, present: bool) -> None:
	monkeypatch.setattr(hardware.SysInfo, 'arch', staticmethod(lambda: arch))

	assert ('microcode' in Initramfs().hooks) is present


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


# A LUKS root on an md array needs both hooks, and mdadm_udev has to run first:
# sd-encrypt cannot open a container on an array that is not assembled yet.
@pytest.mark.parametrize('encrypt_first', [True, False])
def test_raid_hook_precedes_encrypt_either_order(encrypt_first: bool) -> None:
	initramfs = Initramfs()
	calls = [initramfs.add_encrypt, initramfs.add_raid]

	for call in calls if encrypt_first else reversed(calls):
		call()
	initramfs.add_raid()  # second layout pass must not stack the hook

	assert initramfs.hooks.count('mdadm_udev') == 1
	expected = _order(initramfs.hooks, 'block', 'mdadm_udev', 'sd-encrypt', 'filesystems')
	assert expected == sorted(expected)
