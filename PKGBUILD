# shellcheck disable=SC2148,SC2206,SC2034,SC2154
# Local build/dev
# Maintainer: Hadean Eon <hadean-eon-dev@proton.me>
# Maintainer: David Runge <dvzrv@archlinux.org>
# Maintainer: Giancarlo Razzolini <grazzolini@archlinux.org>
# Maintainer: Anton Hvornum <torxed@archlinux.org>
# Contributor: Anton Hvornum <anton@hvornum.se>
# Contributor: Demostanis Worlds <demostanis@protonmail.com>

pkgname=archinstoo
pkgver=0.1.13
pkgrel=5
pkgdesc="Archinstall revamped"
arch=(any)
url="https://github.com/h8d13/archinstoo"
license=(GPL-3.0-only)
#internals first
depends=(
	'python-pyparted'
	'python'
	'arch-install-scripts' #For pacstrap, genfstab, chroot
	'systemd'              #For systemd-based operations
	'coreutils'            #Basic utilities
	'util-linux'           #For partition utilities
	'pciutils'             #For PCI device detection
	'kbd'                  #For keyboard layout configuration
	'libxcrypt'            #For password hashing
	'pacman'
	'git'
)
# base-devel tools are assumed for dev
# note: dev tools are usually handled through pre-commit
# pkgconf gcc parted are needed for for PCH.
makedepends=(
	'python-build'
	'python-installer'
	'python-pylint'
	'python-setuptools'
	'python-wheel'
)

# marked as optional because they depend
# on choices made during installation
# also because they are expected on ISO
# in a 'stable' state of release
# you should obviously feel free to only select the ones you need

optdepends=(
	'btrfs-progs'    #For btrfs filesystem support
	'dosfstools'     #For FAT/EFI filesystem support
	'e2fsprogs'      #For ext4 filesystem support
	'f2fs-tools'     #For f2fs filesystem support
	'ntfs-3g'        #For NTFS filesystem support
	'xfsprogs'       #For XFS filesystem support
	'cryptsetup'     #For LUKS encryption support
	'lvm2'           #For LVM FS layout support
	'pacman-contrib' #For count size and other utilities
	'tree'           #For docs project tree output
	'nvchecker'      #For bumping versions auto
	'archiso'        #For creating your own ISOs
	'qemu-base'      #For testing all of the above
)
# qemu-ui-gtk qemu-audio-pipewire edk2-ovmf

provides=(archinstoo)
replaces=(archinstoo)
source=()
sha512sums=()
b2sums=()

build() {
	cd "$srcdir/../archinstoo" || exit

	sed -i "s/^__version__ = f'[^ ]*/__version__ = f'$pkgver-$pkgrel/" archinstoo/_version.py
	rm -rf dist/ && rm -rf ./*.egg
	python -m build --wheel --no-isolation
}

package() {
	cd "$srcdir/../archinstoo" || exit

	python -m installer --destdir="$pkgdir" dist/*.whl
	install -vDm 644 docs/archinstoo.1 -t "$pkgdir/usr/share/man/man1/"
}
