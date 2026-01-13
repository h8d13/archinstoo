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
  'arch-install-scripts: For pacstrap, genfstab, chroot'
  'coreutils: Basic utilities'
  'systemd: For systemd-based operations'
  'util-linux: For partition utilities'
  'pciutils: For PCI device detection'
  'kbd: For keyboard layout configuration'
  'cryptsetup: For LUKS encryption support'
  'btrfs-progs: For btrfs filesystem support'
  'dosfstools: For FAT/EFI filesystem support'
  'e2fsprogs: For ext4 filesystem support'
  'f2fs-tools: For f2fs filesystem support'
  'ntfs-3g: For NTFS filesystem support'
  'xfsprogs: For XFS filesystem support'
  'lvm2: For LVM FS layout support'
  'python-systemd: For journald logging'
)
provides=(archinstoo)
conflicts=()
replaces=()
source=(
  $pkgname-$pkgver.tar.gz::$url/archive/refs/tags/$pkgver.tar.gz
  $pkgname-$pkgver.tar.gz.sig::$url/releases/download/$pkgver/$pkgname-$pkgver.tar.gz.sig
)
sha512sums=()
b2sums=()
validpgpkeys=('8AA2213C8464C82D879C8127D4B58E897A929F2E') # torxed@archlinux.org

check() {
  cd $pkgname-$pkgver
  ruff check
}

pkgver() {
  cd $pkgname-$pkgver

  awk '$1 ~ /^__version__/ {gsub("\"", ""); print $3}' archinstall/__init__.py
}

build() {
  cd $pkgname-$pkgver

  python -m build --wheel --no-isolation
  PYTHONDONTWRITEBYTECODE=1 make man -C docs
}

package() {
  cd "$pkgname-$pkgver"

  python -m installer --destdir="$pkgdir" dist/*.whl
  install -vDm 644 docs/_build/man/archinstall.1 -t "$pkgdir/usr/share/man/man1/"
}
