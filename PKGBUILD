# shellcheck disable=SC2148,SC2206,SC2034,SC2154
# Local build/dev
# Maintainer: David Runge <dvzrv@archlinux.org>
# Maintainer: Giancarlo Razzolini <grazzolini@archlinux.org>
# Maintainer: Anton Hvornum <torxed@archlinux.org>
# Contributor: Anton Hvornum <anton@hvornum.se>
# Contributor: Demostanis Worlds <demostanis@protonmail.com>
# Contributor: Hadean Eon <hadean-eon-dev@proton.me>

pkgname=archinstoo
pkgver=0.0.01
pkgrel=2
pkgdesc="Archinstall revamped"
arch=(any)
url="https://github.com/h8d13/archinstoo"
license=(GPL-3.0-only)
#internals first
depends=(
  'python-pyparted'
  'python-pydantic'
  'python-pydantic-core'
  'python-annotated-types'
  'python-typing_extensions'
  'python-typing-inspection'
  'python'
  'arch-install-scripts' #For pacstrap, genfstab, chroot
  'coreutils' #Basic utilities
  'util-linux' #For partition utilities
  'pciutils' #For PCI device detection
  'kbd' #For keyboard layout configuration
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
  'systemd' #For systemd-based operations
  'btrfs-progs' #For btrfs filesystem support
  'dosfstools' #For FAT/EFI filesystem support
  'e2fsprogs' #For ext4 filesystem support
  'f2fs-tools' #For f2fs filesystem support
  'ntfs-3g' #For NTFS filesystem support
  'xfsprogs' #For XFS filesystem support
  'cryptsetup' #For LUKS encryption support
  'lvm2' #For LVM FS layout support
  'python-systemd' #System journal logging
  'archiso' #Dev ISO more cow_space
  'tree' #For project tree output
)
provides=(archinstoo)
replaces=(archinstoo)
source=()
sha512sums=()
b2sums=()

check() {
  cd "$srcdir/.." || exit
  ruff check --config pyproject.toml
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
