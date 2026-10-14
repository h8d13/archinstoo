from typing import TYPE_CHECKING

from archinstoo.lib.kernel.initramfs import DRACUT_CONF, Initramfs

if TYPE_CHECKING:
	from pathlib import Path


def test_modules_do_not_stack() -> None:
	# every layout pass calls these, the conf must name each module once
	initramfs = Initramfs()
	for _ in range(2):
		initramfs.add_encrypt()
		initramfs.add_lvm()
		initramfs.add_raid()

	assert initramfs.modules == ['crypt', 'lvm', 'mdraid']


def test_conf_lists_modules_drivers_and_files(tmp_path: Path) -> None:
	initramfs = Initramfs()
	initramfs.add_encrypt()
	initramfs.add_fido2()
	initramfs.files.append('/etc/cryptsetup-keys.d/root.key')
	initramfs.write_conf(tmp_path)

	lines = (tmp_path / DRACUT_CONF).read_text().splitlines()
	assert lines == [
		'add_dracutmodules+=" crypt fido2 "',
		'install_items+=" /etc/cryptsetup-keys.d/root.key "',
	]


def test_empty_conf_is_still_written(tmp_path: Path) -> None:
	# kernel-install runs dracut either way; an empty drop-in is harmless
	Initramfs().write_conf(tmp_path)
	assert not (tmp_path / DRACUT_CONF).read_text()
