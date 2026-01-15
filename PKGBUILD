# shellcheck disable=SC2148,SC2206,SC2034,SC2154
# Maintainer: David Runge <dvzrv@archlinux.org>
# Maintainer: Giancarlo Razzolini <grazzolini@archlinux.org>
# Maintainer: Anton Hvornum <torxed@archlinux.org>
# Contributor: Anton Hvornum <anton@hvornum.se>
# Contributor: Demostanis Worlds <demostanis@protonmail.com>
# Contributor: Hadean Eon <hadean-eon-dev@proton.me>

pkgname=archinstoo
pkgver=0.0.01
pkgrel=0
pkgdesc="Archinstall revamped"
arch=(any)
url="https://github.com/h8d13/archinstoo"
license=(GPL-3.0-only)
depends=(
  'python-pyparted'
  'python-pydantic'
  'python-pydantic-core'
  'python-annotated-types'
  'python-typing_extensions'
  'python-typing-inspection'
  'python'
)
makedepends=(
  'python-build'
  'python-installer'
  'python-pylint'
  'python-setuptools'
  'python-sphinx'
  'python-sphinx_rtd_theme'
  'python-wheel'
  'ruff'
)
# marked as optional because they depend
# on choices made during installation
# also because they are expected on ISO
# in a 'stable' state of release
optdepends=(
  'arch-install-scripts' #For pacstrap, genfstab, chroot
  'coreutils' #Basic utilities
  'systemd' #For systemd-based operations
  'python-systemd' #System journal logging
  'util-linux' #For partition utilities
  'pciutils' #For PCI device detection
  'kbd' #For keyboard layout configuration
  'btrfs-progs' #For btrfs filesystem support
  'dosfstools' #For FAT/EFI filesystem support
  'e2fsprogs' #For ext4 filesystem support
  'f2fs-tools' #For f2fs filesystem support
  'ntfs-3g' #For NTFS filesystem support
  'xfsprogs' #For XFS filesystem support
  'cryptsetup' #For LUKS encryption support
  'lvm2' #For LVM FS layout support
)
provides=(archinstoo)
conflicts=()
replaces=()
source=()
sha512sums=()
b2sums=()

check() {
  cd "$srcdir/.." || exit
  ruff check
}

build() {
  cd "$srcdir/.." || exit

  rm -rf dist/ && rm -rf ./*.egg
  python -m build --wheel --no-isolation
  PYTHONDONTWRITEBYTECODE=1 make man -C docs
}

package() {
  cd "$srcdir/.." || exit

  python -m installer --destdir="$pkgdir" dist/*.whl
  install -vDm 644 docs/_build/man/archinstall.1 -t "$pkgdir/usr/share/man/man1/"
}
