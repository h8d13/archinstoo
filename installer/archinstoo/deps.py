# What archinstoo needs on the system it runs from, Arch package names.
# --script bootstrap installs both sets into its root; the ISO and an Arch
# host bring the disk tools already.
# https://gitlab.archlinux.org/archlinux/archiso/-/blob/master/configs/releng/packages.x86_64
# mirror the PKGBUILDs in repo (tests/test_prepare.py checks)

# comment columns are read as a table, ruff would collapse them
# fmt: off
BASE = (
	'coreutils',  	        # Basic utilities
	'util-linux',  	        # For partition utilities
	'pciutils',  	        # For PCI device detection
	'kbd',  	        # For keyboard layout configuration
	'pacman',
	'git',  	        # Cloning stashes
	'arch-install-scripts', # For pacstrap, chroot
	'python-pyparted',
	'dosfstools',  	        # FAT EFI filesystem support
)
DISK = (
	'btrfs-progs', 		# btrfs filesystem support
	'e2fsprogs',  		# ext4 filesystem support
	'f2fs-tools',  		# f2fs filesystem support
	'xfsprogs',  		# XFS filesystem support
	'cryptsetup',  		# LUKS encryption support
	'lvm2',  		# LVM layout support
	'mdadm',		# RAID layout support
)
# fmt: on
