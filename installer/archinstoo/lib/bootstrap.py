# Any-host bootstrap behind `--script bootstrap`, following
# https://wiki.archlinux.org/title/Install_Arch_Linux_from_existing_Linux
# Runs on the host's python before any of archinstoo's deps exist: stdlib-
# backed lib helpers only (no pyparted). Host requirements: scripts/bootstrap.py

import hashlib
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import NamedTuple

from archinstoo import deps
from archinstoo.lib.exceptions import FetchError, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.output import info, warn
from archinstoo.lib.utils.env import Env
from archinstoo.lib.utils.host import is_root
from archinstoo.lib.utils.net import download_file_from_url

BOOT_DIR = Env.get_path('BOOT_DIR') or Path('/tmp/A2-boot')  # noqa: S108 - root-only, BOOT_DIR overrides
BOOT_MIRROR = Env.get_value('BOOT_MIRROR', 'https://geo.mirror.pkgbuild.com')

ARCH = SysInfo.arch()
ROOT = BOOT_DIR / f'root.{ARCH}'
# the directory holding the package (installer/ in a checkout), bound into
# the root and run from there: relative --config paths resolve as with ./RUN
SRC = Path(__file__).resolve().parents[2]
INSIDE = Path('/root/archinstoo')
# the tarball ships Arch's keyring only, pacman needs the port's too
PORT_KEY = ROOT / 'etc/pacman.d/boot-port.key'
# python first: a lone python in the tarball may want a newer glibc than it
# ships. efibootmgr: the NVRAM entries are written from here, the ISO has its own
DEPENDS = ('python', *deps.BASE, *deps.DISK, 'efibootmgr')


class Source(NamedTuple):
	tarball: str
	sig: str
	sums: str | None  # sha256sums.txt, None where the port publishes none
	key_wkd: str | None  # signer's address for a WKD lookup, or
	key_url: str | None  # a key file to import
	key_fpr: str


class BootError(RuntimeError):
	pass


def source() -> Source | None:
	# archlinux.org is x86_64 only, aarch64 follows Arch Linux Ports
	# (architecture/)
	if ARCH == 'x86_64':
		# wiki: signature and sums from archlinux.org, not a mirror
		release = 'https://archlinux.org/iso/latest'
		name = 'archlinux-bootstrap-x86_64.tar.zst'
		return Source(
			tarball=f'{BOOT_MIRROR}/iso/latest/{name}',
			sig=f'{release}/{name}.sig',
			sums=f'{release}/sha256sums.txt',
			key_wkd='pierre@archlinux.org',
			key_url=None,
			key_fpr='3E80CA1A8B89F69CBA57D98A76A5EF9054449A5C',
		)
	if ARCH == 'aarch64':
		ports = 'https://arch-linux-repo.drzee.net/arch'
		tarball = f'{ports}/tarballs/os/aarch64/archlinux-bootstrap-latest-aarch64.tar.zst'
		return Source(
			tarball=tarball,
			sig=f'{tarball}.sig',
			sums=None,
			key_wkd=None,
			key_url=f'{ports}/extra/os/aarch64/public.key',
			key_fpr='9B2C213B21883BB65CE2FB900CF25682E6BA0751',
		)
	return None


def fetch(url: str, retries: int = 3) -> Path:
	dest = BOOT_DIR / url.rsplit('/', 1)[-1]
	info(f'Fetching {url}')
	for attempt in range(1, retries + 1):
		try:
			download_file_from_url(url, dest)
			return dest
		except (FetchError, OSError) as err:
			if attempt == retries:
				raise BootError(f'{url}: {err}') from err
			warn(f'{url}: {err}, retry {attempt}/{retries - 1}')
			time.sleep(2 * attempt)
	raise AssertionError('unreachable')


def sha256(path: Path) -> str:
	h = hashlib.sha256()
	with path.open('rb') as f:
		for chunk in iter(lambda: f.read(1 << 20), b''):
			h.update(chunk)
	return h.hexdigest()


def verify_sum(tarball: Path, sums: Path) -> None:
	pattern = rf'^([0-9a-f]{{64}})\s+{re.escape(tarball.name)}$'
	if not (m := re.search(pattern, sums.read_text(), re.MULTILINE)):
		raise BootError(f'{tarball.name} not listed in {sums.name}')
	if sha256(tarball) != m.group(1):
		raise BootError(f'{tarball.name} does not match {sums.name}')
	info(f'{tarball.name}: checksum OK')


def _gpg_status(src: Source, gpg: list[str], tarball: Path, sig: Path) -> str:
	if src.key_url:
		SysCommand([*gpg, '--import', str(fetch(src.key_url))])
	else:
		SysCommand([*gpg, '--auto-key-locate', 'clear,wkd', '--locate-external-key', str(src.key_wkd)])
	try:
		return SysCommand([*gpg, '--trusted-key', src.key_fpr, '--status-fd', '1', '--verify', str(sig), str(tarball)]).decode()
	except SysCallError as err:
		return err.worker_log.decode(errors='ignore')


def verify_sig(src: Source, tarball: Path, sig: Path) -> None:
	gnupg = BOOT_DIR / 'gnupg'
	gnupg.mkdir(mode=0o700, exist_ok=True)
	try:
		status = _gpg_status(src, ['gpg', '--homedir', str(gnupg)], tarball, sig)
	finally:
		# gpg started an agent (and dirmngr for WKD) for this homedir:
		# nothing needs them after, they would outlive the run on the host
		SysCommand(['gpgconf', '--homedir', str(gnupg), '--kill', 'all'])
	# pin the signer, not just any valid signature. --trusted-key only quiets
	# the web of trust warning, VALIDSIG is the real check
	if not re.search(rf'^\[GNUPG:\] VALIDSIG {src.key_fpr} ', status, re.MULTILINE):
		raise BootError(f'{tarball.name} not signed by {src.key_fpr}')
	info(f'{tarball.name}: signature OK')


def unpack(src: Source) -> None:
	tarball = fetch(src.tarball)
	sig = fetch(src.sig)
	if src.sums:
		sums = fetch(src.sums)
		verify_sum(tarball, sums)
		sums.unlink()

	if shutil.which('gpg'):
		verify_sig(src, tarball, sig)
	elif src.sums:
		warn(f'no gpg, checksum only, trusting TLS to {src.sums.rsplit("/", 1)[0]}')
	else:
		raise BootError(f'no checksums published for {ARCH}, gpg is required')
	sig.unlink()

	# bsdtar: restores the LIBARCHIVE.xattr file capabilities GNU/busybox tar
	# and python's tarfile drop
	SysCommand(['bsdtar', '-x', '--numeric-owner', '-f', str(tarball), '-C', str(BOOT_DIR)])
	tarball.unlink()
	if src.key_url:
		shutil.copy(BOOT_DIR / src.key_url.rsplit('/', 1)[-1], PORT_KEY)


def configure_pacman() -> None:
	# Arch Ports puts Server lines in pacman.conf, no mirrorlist to fill there
	conf = (ROOT / 'etc/pacman.conf').read_text()
	mirrorlist = ROOT / 'etc/pacman.d/mirrorlist'
	if not re.search(r'^Include = /etc/pacman.d/mirrorlist', conf, re.MULTILINE):
		return
	if re.search(r'^Server', mirrorlist.read_text(), re.MULTILINE):
		return
	with mirrorlist.open('a') as f:
		f.write(f'Server = {BOOT_MIRROR}/$repo/os/$arch\n')


def mount(*args: str) -> None:
	SysCommand(['mount', *args])


def bind_into_root(host: Path, *flags: str) -> None:
	inside = ROOT / host.relative_to('/')
	inside.mkdir(parents=True, exist_ok=True)
	mount(*flags, str(host), str(inside))


def is_mounted(path: Path) -> bool:
	# mountinfo, not Path.is_mount(): that compares st_dev with the parent,
	# and the root's self-bind sits on the same filesystem
	try:
		SysCommand(['mountpoint', '-q', str(path)])
	except SysCallError:
		return False
	return True


def teardown() -> None:
	# also catches what a killed run left mounted
	if is_mounted(ROOT):
		SysCommand(['umount', '-R', str(ROOT)])


def chroot_setup() -> None:
	# arch-chroot's set by hand, no arch-chroot needed on the host. The self
	# bind is pacman's CheckSpace mountpoint, private so a shared parent (/tmp
	# on the ISO) gets no copy of the mounts below that teardown never sees
	root = str(ROOT)
	mount('--bind', '--make-private', root, root)
	mount('-t', 'proc', 'proc', f'{root}/proc', '-o', 'nosuid,noexec,nodev')
	# rslave: teardown's umount -R must not propagate back to the host's
	# /sys and /dev submounts
	bind_into_root(Path('/sys'), '--rbind', '--make-rslave')
	bind_into_root(Path('/dev'), '--rbind', '--make-rslave')
	# a layout mounted by hand on the host (pre-mounted config) has to be
	# where the installer looks; rslave for the same teardown reason
	bind_into_root(Path('/mnt'), '--rbind', '--make-rslave')
	# /run/udev: lsblk UUIDs, same reason as the udev check
	bind_into_root(Path('/run'), '--bind', '--make-private')
	mount('-t', 'tmpfs', 'tmp', str(ROOT / 'tmp'), '-o', 'mode=1777,strictatime,nodev,nosuid')
	# the tarball has no resolv.conf to bind over; a host without one has no
	# DNS to hand in either (arch-chroot skips it the same way)
	if Path('/etc/resolv.conf').exists():
		resolv = ROOT / 'etc/resolv.conf'
		resolv.touch()
		mount('--bind', '/etc/resolv.conf', str(resolv))
	# the iso network type copies what the live host was set up with (iwd
	# PSKs, networkd units); the tarball's own are empty
	for host_dir in (Path('/var/lib/iwd'), Path('/etc/systemd/network')):
		if host_dir.is_dir():
			bind_into_root(host_dir, '--bind')
	inside = ROOT / INSIDE.relative_to('/')
	inside.mkdir(parents=True, exist_ok=True)
	mount('--bind', str(SRC), str(inside))


def install_deps_cmd() -> str:
	# the root is reused across runs: once the deps are in, skip syncing at
	# all. -Syu: the tarball has no sync dbs
	names = ' '.join(DEPENDS)
	return f'pacman -T {names} || pacman -Syu --needed --noconfirm {names}'


def run_inside(src: Source, args: list[str]) -> int:
	script = f"""
		set -e
		if [ ! -e /etc/pacman.d/gnupg/trustdb.gpg ]; then
			pacman-key --init
			pacman-key --populate
			# pacstrap copies this gnupg into the target
			if [ -e /etc/pacman.d/boot-port.key ]; then
				pacman-key --add /etc/pacman.d/boot-port.key
				pacman-key --lsign-key {src.key_fpr}
			fi
		fi
		# old Debian: /dev/shm -> /run/shm, else pacstrap cannot mount it
		if [ -L /dev/shm ]; then
			mkdir -p /run/shm
		fi
		{install_deps_cmd()}
		cd {INSIDE}
		exec python -B -m archinstoo "$@"
	"""
	# A2_BOOTSTRAP: '/' is this throwaway root, archinstoo blocks live/packages
	# A2_BOOT_ROOT: archinstoo names its log by the path the host sees
	env = Env.get_envir({'A2_BOOTSTRAP': '1', 'A2_BOOT_ROOT': str(ROOT)})
	# own pid namespace, as arch-chroot does: what the run leaves behind
	# (pacman-key's gpg-agent) dies with it instead of holding the root busy.
	# This console, not SysCommand's pty: the menus read our stdin
	argv = ['unshare', '--fork', '--pid', '--kill-child', 'chroot', str(ROOT), '/bin/bash', '-c', script, 'boot', *args]
	return subprocess.run(argv, env=env, check=False).returncode  # noqa: S603 - fixed argv, tools from $PATH


def preflight() -> Source:
	if not is_root():
		raise BootError('must run as root')
	if (src := source()) is None:
		raise BootError(f'no bootstrap tarball for {ARCH} (x86_64, aarch64)')
	# without it lsblk has no UUIDs and the fstab silently names /dev/vdaN
	if not Path('/run/udev/control').is_socket():
		raise BootError('no udev (alpine: apk add eudev && setup-devd udev)')
	return src


def _interrupted(signum: int, _frame: object) -> None:
	# TERM/HUP unwind like ^C, so teardown still runs
	raise SystemExit(128 + signum)


def bootstrap(args: list[str]) -> int:
	src = preflight()
	BOOT_DIR.mkdir(parents=True, exist_ok=True)
	if not (ROOT / 'usr/bin/pacman').exists():
		unpack(src)
	configure_pacman()

	# rm -rf the root only after this exits: a live run has /dev mounted inside
	teardown()
	signal.signal(signal.SIGTERM, _interrupted)
	signal.signal(signal.SIGHUP, _interrupted)
	try:
		chroot_setup()
		return run_inside(src, args)
	finally:
		teardown()
