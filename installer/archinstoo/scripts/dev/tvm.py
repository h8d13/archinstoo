# sudo pacman -S --needed qemu-base qemu-ui-gtk qemu-audio-pipewire edk2-ovmf
# (swap qemu-ui-gtk for qemu-ui-sdl/qemu-ui-curses if you prefer; set A2_DISPLAY_BACKEND to match)
# (audio backend is a separate pkg: qemu-audio-pipewire (default), qemu-audio-pa, qemu-audio-alsa; set A2_AUDIO_BACKEND to match)
# (A2_ARCH=aarch64 adds: qemu-system-aarch64 edk2-aarch64; qemu-hw-display-virtio-gpu{,-pci} for A2_VGA=virtio-gpu-pci)
#
# Dev test VM for archinstoo. Boots an ISO under QEMU.
# ISO building is intentionally NOT done here, use isos/ISOMOD for that/default Arch ISO.
# Credits to @Softer, modified for archinstoo.
#
# Host artifacts (created in repo root, git-ignored):
#   .dev-disk.qcow2     VM disk image (qemu-img)
#   .dev-ovmf-vars.fd   persistent UEFI NVRAM (copied from OVMF_VARS)
#                       (both get a -<arch> suffix when A2_ARCH is not x86_64,
#                       so an aarch64 install never clobbers the x86_64 one)
#   A2_SERIAL=1 only:
#   .dev-boot/          kernel + initramfs pulled out of the ISO
#   .dev-serial.sock    guest ttyS0, .dev-serial.log its full transcript
#   .dev-capture.log    guest ttyS1, byte-exact (tser capture)
#   .dev-monitor.sock   QEMU HMP monitor, .dev-vm.pid the daemon pid
#
# Usage (from the repo root, tvm = ./RUN --script dev.tvm, tser = ./RUN --script dev.tser):
#   tvm            - fresh disk, boot ISO
#   tvm keep   | k - reuse disk, boot ISO
#   tvm boot   | b - boot from installed disk (no ISO)
#   tvm clean  | c - remove disk and NVRAM (ISOs untouched)
#   tvm help   | h - show this help
# Env overrides (on/off ones take 1/yes/true/on, anything else is off):
#   A2_ARCH             guest architecture: 'x86_64' (default) or 'aarch64'.
#                       aarch64 boots -machine virt with edk2-aarch64 pflash,
#                       KVM only when the host is aarch64 too (TCG -cpu max
#                       otherwise: slow, expect minutes to a shell). ISO
#                       discovery filters on the arch in the filename. No
#                       -cdrom on virt: the ISO rides virtio-scsi, boot order
#                       goes through bootindex. Input is USB (xhci kbd+tablet).
#                       A2_BIOS and A2_UKI are x86_64 only.
#   A2_SERIAL           '1' boots headless with the console on ttyS0 and
#                       detaches (no window, no stdio monitor). Composes with
#                       every mode above. Drive it with tser (attach, or login/run).
#                       With A2_GL=1 the virgl window stays: sockets still
#                       detach, so a real session is on screen while the
#                       guest is driven over serial (tser type/keys for the
#                       greeter, screendump via mon).
#                       ISO modes direct-boot the ISO's own kernel via -kernel so
#                       console=ttyS0 can be forced; OVMF still boots it EFI-stub,
#                       so the guest keeps a real UEFI environment. Needs bsdtar.
#                       'boot' mode has no such hook: the installed system only
#                       talks to ttyS0 if its own cmdline says console=ttyS0.
#                       aarch64 extracts the same way (arch/boot/aarch64/).
#                       virt's own UART is a pl011 whose QEMU model stalls on
#                       typed input past a few hundred bytes, so both lines
#                       ride a dual-port PCI 16550 instead: ttyS0/ttyS1 in
#                       the guest, same as q35, same sockets on the host.
#                       'tty' is the same boot, but ttyS0 is this terminal:
#                       foreground, boot log and login right here, no tser.
#                       Ctrl-a x quits, Ctrl-a c toggles the QEMU monitor.
#   A2_BIOS             '1' boots SeaBIOS instead of OVMF: no pflash, no
#                       NVRAM. The installed disk must carry a BIOS-capable
#                       bootloader (grub with a bios_grub partition).
#   A2_DEV_ISO          explicit ISO path (skips discovery)
#   A2_UKI              path to a live UKI (isos/UKIMOD output, isos/a/archinstoo.efi).
#                       Boots it via -kernel in place of an ISO: no cdrom, no
#                       kernel extraction, its baked cmdline already has ttyS0.
#                       Disk handling per mode is unchanged. OVMF only.
#   A2_RAM, A2_CPUS     VM resources (default 4G, 4)
#   A2_DISK_SIZE        new disk size (default 64G)
#   A2_DISPLAY_BACKEND  qemu -display value (default 'gtk,zoom-to-fit=off')
#   A2_VGA              qemu -vga value (default 'std'; 'virtio' needs qemu-hw-display-virtio-vga)
#                       On aarch64 it is a -device name instead (default 'ramfb',
#                       built in; 'virtio-gpu-pci' needs qemu-hw-display-virtio-gpu{,-pci})
#   A2_GL               '1' swaps video for virtio-vga-gl + display gl=on (virgl 3D accel).
#                       Overrides A2_VGA. niri/DMS have no software fallback, black-screen
#                       without this. Needs the full module chain (vga-gl alone won't load):
#                       qemu-hw-display-virtio-{gpu,gpu-gl,vga,vga-gl} + qemu-ui-opengl
#                       (aarch64: virtio-gpu-gl-pci, qemu-hw-display-virtio-gpu{,-gl,-pci,-gl-pci})
#   A2_QEMU_EXTRA       raw qemu args appended last (word-split, no quoting inside)
#                       a cloud image (distros/DEB, distros/FED) takes its
#                       cloud-init config off the SMBIOS serial, see distros/CLOUD
#   A2_DRY              '1' prints the assembled qemu command and exits (still
#                       creates the disk/NVRAM the mode asks for)
#   A2_AUDIO_BACKEND    qemu -audiodev value (default 'pipewire'; 'pa'/'alsa' need the matching qemu-audio-* pkg)

import argparse
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from archinstoo.lib.output import error, info
from archinstoo.lib.utils.env import Env
from archinstoo.scripts.dev._vm import CAPTURE, LOG, MONITOR, PIDFILE, ROOT, SERIAL, vm_pid

ISOMOD_OUT = ROOT / 'isos' / 'a'
DEV_ISO_DIR = ROOT / '.dev-iso'
BOOT_DIR = ROOT / '.dev-boot'
ARCHISO_ENTRY = 'loader/entries/01-archiso-linux.conf'

# (package, [(code, vars), ...]) per guest arch, first pair present wins
FIRMWARE = {
	'x86_64': (
		'edk2-ovmf',
		[
			('/usr/share/edk2/x64/OVMF_CODE.4m.fd', '/usr/share/edk2/x64/OVMF_VARS.4m.fd'),
			('/usr/share/edk2-ovmf/x64/OVMF_CODE.fd', '/usr/share/edk2-ovmf/x64/OVMF_VARS.fd'),
			('/usr/share/edk2/ovmf/OVMF_CODE.fd', '/usr/share/edk2/ovmf/OVMF_VARS.fd'),
			('/usr/share/OVMF/OVMF_CODE_4M.fd', '/usr/share/OVMF/OVMF_VARS_4M.fd'),
			('/usr/share/OVMF/OVMF_CODE.fd', '/usr/share/OVMF/OVMF_VARS.fd'),
		],
	),
	# virt pflash wants both images padded to 64M, Arch/Debian ship them so
	'aarch64': (
		'edk2-aarch64',
		[
			('/usr/share/edk2/aarch64/QEMU_EFI.fd', '/usr/share/edk2/aarch64/QEMU_VARS.fd'),
			('/usr/share/edk2/aarch64/QEMU_CODE.fd', '/usr/share/edk2/aarch64/QEMU_VARS.fd'),
			('/usr/share/AAVMF/AAVMF_CODE.fd', '/usr/share/AAVMF/AAVMF_VARS.fd'),
		],
	),
}

# short aliases, same as the modes they stand for
MODES = {'default': 'default', 'keep': 'keep', 'k': 'keep', 'boot': 'boot', 'b': 'boot', 'clean': 'clean', 'c': 'clean', 'help': 'help', 'h': 'help'}


@dataclass(frozen=True)
class Opts:
	arch: str
	serial: str
	bios: bool
	gl: bool
	dry: bool
	uki: Path | None
	iso: Path | None
	disk_size: str
	ram: str
	cpus: str
	display: str
	vga: str
	audio: str
	extra: tuple[str, ...]

	@property
	def x86(self) -> bool:
		return self.arch == 'x86_64'

	@property
	def qemu(self) -> str:
		return f'qemu-system-{self.arch}'

	@property
	def disk(self) -> Path:
		return ROOT / f'.dev-disk{self.suffix}.qcow2'

	@property
	def ovmf_vars(self) -> Path:
		return ROOT / f'.dev-ovmf-vars{self.suffix}.fd'

	@property
	def suffix(self) -> str:
		return '' if self.x86 else f'-{self.arch}'

	@property
	def gl_device(self) -> str:
		return 'virtio-vga-gl' if self.x86 else 'virtio-gpu-gl-pci'


def read_opts() -> Opts:
	arch = Env.get_value('A2_ARCH', 'x86_64')
	if arch not in FIRMWARE:
		error(f'A2_ARCH={arch} unsupported (x86_64, aarch64)')
		raise SystemExit(1)

	# 'tty' is its own mode, anything else is a boolean like A2_BIOS/A2_GL
	serial = Env.get_value('A2_SERIAL', '').strip().lower()
	if serial != 'tty':
		serial = '1' if Env.get_bool('A2_SERIAL') else '0'

	return Opts(
		arch=arch,
		serial=serial,
		bios=Env.get_bool('A2_BIOS'),
		gl=Env.get_bool('A2_GL'),
		dry=Env.get_bool('A2_DRY'),
		# ./RUN cds into installer/, so a relative path means the repo root
		uki=Env.get_path('A2_UKI', ROOT),
		iso=Env.get_path('A2_DEV_ISO', ROOT),
		disk_size=Env.get_value('A2_DISK_SIZE', '64G'),
		ram=Env.get_value('A2_RAM', '4G'),
		cpus=Env.get_value('A2_CPUS', '4'),
		display=Env.get_value('A2_DISPLAY_BACKEND', 'gtk,zoom-to-fit=off'),
		# x86_64: a -vga value. aarch64 virt has no VGA slot, so a -device name:
		# ramfb is compiled in, virtio-gpu-pci is a module.
		vga=Env.get_value('A2_VGA', 'std' if arch == 'x86_64' else 'ramfb'),
		audio=Env.get_value('A2_AUDIO_BACKEND', 'pipewire'),
		# raw qemu args, word-split: an extra disk with a serial, a second NIC, ...
		extra=tuple(Env.get_value('A2_QEMU_EXTRA', '').split()),
	)


def header() -> str:
	# --help is the comment block this file opens with
	lines = []
	for line in Path(__file__).read_text().splitlines():
		if not line.startswith('#'):
			break
		lines.append(line.removeprefix('#').removeprefix(' '))
	return '\n'.join(lines)


def probe_ovmf(opts: Opts) -> tuple[Path, Path] | None:
	if opts.bios:
		return None
	pkg, pairs = FIRMWARE[opts.arch]
	for code, nvram in pairs:
		if Path(code).is_file() and Path(nvram).is_file():
			return Path(code), Path(nvram)
	error(f"UEFI firmware for {opts.arch} not found. Install '{pkg}' or similar on your distro.")
	raise SystemExit(1)


def ensure_virgl(opts: Opts) -> None:
	# virgl needs both ends: GL-capable device AND gl=on on the display.
	# -device help skips unloaded modules; probe with device-specific help instead.
	probe = subprocess.run([opts.qemu, '-device', f'{opts.gl_device},help'], capture_output=True, text=True, check=False)
	if 'not found' in probe.stdout + probe.stderr:
		error(f'{opts.gl_device} not loadable (install qemu-hw-display-virtio-{{gpu,gpu-gl,vga,vga-gl}} / -{{gpu-pci,gpu-gl-pci}} and qemu-ui-opengl)')
		raise SystemExit(1)


def check_host_deps(opts: Opts, attach_iso: bool) -> None:
	if missing := [cmd for cmd in (opts.qemu, 'qemu-img') if not shutil.which(cmd)]:
		error(f'missing host commands: {" ".join(missing)} (install qemu-base / qemu-system-{opts.arch})')
		raise SystemExit(1)
	if not opts.x86 and opts.bios:
		error('A2_BIOS is x86_64 only (no SeaBIOS on virt)')
		raise SystemExit(1)
	if not opts.x86 and opts.uki:
		error('A2_UKI is x86_64 only (UKIMOD builds x86_64 images)')
		raise SystemExit(1)
	# bsdtar reads the kernel out of the ISO, no mount (and no root) needed
	if attach_iso and opts.serial != '0' and not opts.uki and not shutil.which('bsdtar'):
		error(f'A2_SERIAL={opts.serial} needs bsdtar to read the ISO (install libarchive)')
		raise SystemExit(1)


def ensure_no_running_vm() -> None:
	if pid := vm_pid():
		error(f'VM already running (pid {pid}), stop it with ./RUN --script dev.tser quit')
		raise SystemExit(1)
	PIDFILE.unlink(missing_ok=True)


def bsdtar_x(iso: Path, member: str, dest: Path) -> None:
	with dest.open('wb') as fh:
		rc = subprocess.run(['bsdtar', '-xOf', str(iso), member], stdout=fh, check=False).returncode
	if rc:
		error(f'bsdtar could not extract {member} from {iso}')
		raise SystemExit(rc)


def bsdtar_read(iso: Path, member: str) -> str:
	result = subprocess.run(['bsdtar', '-xOf', str(iso), member], stdout=subprocess.PIPE, check=False)
	if result.returncode:
		error(f'bsdtar could not extract {member} from {iso}')
		raise SystemExit(result.returncode)
	return result.stdout.decode(errors='replace')


def extract_iso_kernel(opts: Opts, iso: Path) -> str:
	# The ISO's bootloader entries carry no serial console, and editing them at
	# the systemd-boot menu over serial is not scriptable. Pull the kernel and
	# initramfs out of the ISO instead and hand them to QEMU directly, reusing
	# the entry's own cmdline (archisosearchuuid changes every release) with
	# console=ttyS0 appended. The ISO stays attached as a cdrom: the archiso hook
	# still finds the squashfs on it.
	stamp = BOOT_DIR / '.stamp'
	vmlinuz, initrd, cmdline = BOOT_DIR / 'vmlinuz', BOOT_DIR / 'initrd', BOOT_DIR / 'cmdline'
	want = f'{iso}:{int(iso.stat().st_mtime)}'
	BOOT_DIR.mkdir(parents=True, exist_ok=True)

	# a missing output re-extracts too: a stamp can outlive the file names
	cached = stamp.is_file() and stamp.read_text().strip() == want and initrd.is_file() and initrd.stat().st_size > 0
	if not cached:
		info(f'extracting kernel/initramfs from {iso.name}')
		for name in ('vmlinuz', 'initrd', 'cmdline', 'grub.cfg'):
			(BOOT_DIR / name).unlink(missing_ok=True)

		if subprocess.run(['bsdtar', '-tf', str(iso), ARCHISO_ENTRY], capture_output=True, check=False).returncode == 0:
			kernel_member = f'arch/boot/{opts.arch}/vmlinuz-linux'
			initrd_member = f'arch/boot/{opts.arch}/initramfs-linux.img'
			entry = bsdtar_read(iso, ARCHISO_ENTRY).splitlines()
			options = [m.group(1) for line in entry if (m := re.match(r'options\s+(.*)', line))]
			cmdline.write_text(''.join(f'{opt}\n' for opt in options))
		else:
			# other live ISOs (alpine): first grub entry has kernel, cmdline, initrd
			bsdtar_x(iso, 'boot/grub/grub.cfg', BOOT_DIR / 'grub.cfg')
			fields = [line.split() for line in (BOOT_DIR / 'grub.cfg').read_text(errors='replace').splitlines()]
			linux = next((f for f in fields if f[:1] == ['linux']), [])
			initrd_line = next((f for f in fields if f[:1] == ['initrd']), [])
			kernel_member = linux[1].removeprefix('/') if len(linux) > 1 else ''
			initrd_member = initrd_line[1].removeprefix('/') if len(initrd_line) > 1 else ''
			cmdline.write_text(f'{" ".join(linux[2:])}\n' if linux else '')

		bsdtar_x(iso, kernel_member, vmlinuz)
		bsdtar_x(iso, initrd_member, initrd)
		stamp.write_text(f'{want}\n')

	if not (vmlinuz.is_file() and vmlinuz.stat().st_size > 0):
		error(f'no kernel in {iso} (archiso or grub layout?)')
		raise SystemExit(1)
	if not (cmdline.is_file() and cmdline.stat().st_size > 0):
		error(f'no boot cmdline in {iso} (archiso or grub layout?)')
		raise SystemExit(1)
	return cmdline.read_text().rstrip('\n')


def find_iso(opts: Opts) -> Path | None:
	if opts.iso:
		if not opts.iso.is_file():
			error(f'A2_DEV_ISO={opts.iso} not found')
			raise SystemExit(1)
		return opts.iso
	# newest first, then keep the guest arch: aarch64 ISOs carry it in the
	# name (archlinux-*-aarch64.iso), x86_64 ones do not always (archlinux-*.iso)
	isos = sorted([*ISOMOD_OUT.glob('*.iso'), *DEV_ISO_DIR.glob('*.iso')], key=lambda p: p.stat().st_mtime, reverse=True)
	if opts.x86:
		return next((p for p in isos if 'aarch64' not in str(p)), None)
	return next((p for p in isos if opts.arch in str(p)), None)


def require_iso(opts: Opts) -> Path:
	if iso := find_iso(opts):
		return iso
	error(f'No ISO found. Build one with isos/ISOMOD, drop one in {DEV_ISO_DIR}/ or {ISOMOD_OUT}, or set A2_DEV_ISO=/path/to.iso')
	raise SystemExit(1)


def require_media(opts: Opts) -> None:
	# ISO by default, a UKI when asked for: both are "boot media" to the modes
	if not opts.uki:
		require_iso(opts)
		return
	if not opts.uki.is_file():
		error(f'A2_UKI={opts.uki} not found (build one with isos/UKIMOD)')
		raise SystemExit(1)
	if opts.bios:
		error('A2_UKI needs OVMF, unset A2_BIOS')
		raise SystemExit(1)


def require_disk(opts: Opts) -> None:
	if not opts.disk.is_file():
		error('Disk missing, run without args first')
		raise SystemExit(1)


def clean(opts: Opts) -> None:
	ensure_no_running_vm()
	for path in (opts.disk, opts.ovmf_vars, SERIAL, LOG, CAPTURE, MONITOR):
		if path.exists() or path.is_symlink():
			path.unlink()
			info(f"removed '{path}'")
	if BOOT_DIR.exists():
		shutil.rmtree(BOOT_DIR)
		info(f"removed directory '{BOOT_DIR}'")


def console_args(opts: Opts) -> list[str]:
	# commas are qemu device/chardev value syntax throughout
	if opts.gl:
		video = ['-device', opts.gl_device, '-display', f'{opts.display},gl=on']
	elif opts.serial != '0':
		video = ['-display', 'none']
	elif opts.x86:
		video = ['-vga', opts.vga, '-display', opts.display]
	else:
		video = ['-device', opts.vga, '-display', opts.display]

	if opts.serial == '1':
		# Headless and detached: the console is a unix socket with a logfile, so
		# tser can connect, act and exit instead of holding a session open.
		# Audio is dropped, no session to play into.
		# ttyS1 is a plain file chardev, and that is the point: the socket's
		# logfile duplicates bytes replayed after a partial write, so guest
		# output redirected to /dev/ttyS1 is the only byte-exact transcript
		# (tser capture). ttyS0 stays the interactive end.
		args = [
			*video,
			'-chardev',
			f'socket,id=ser0,path={SERIAL},server=on,wait=off,logfile={LOG},logappend=on',
			'-chardev',
			f'file,id=cap0,path={CAPTURE}',
		]
		if opts.x86:
			args += ['-serial', 'chardev:ser0', '-serial', 'chardev:cap0']
		else:
			# q35's ISA 16550s become one dual-port PCI 16550 on virt, so the
			# guest still sees ttyS0/ttyS1. The pl011 stays off the sockets: its
			# QEMU model stops taking input after ~280 bytes in one line.
			args += ['-device', 'pci-serial-2x,chardev1=ser0,chardev2=cap0', '-serial', 'none']
		return [*args, '-monitor', f'unix:{MONITOR},server=on,wait=off', '-pidfile', str(PIDFILE), '-daemonize']

	if opts.serial == 'tty':
		# ttyS0 and the monitor share stdio (mux), Ctrl-a switches between them
		args = [*video, '-chardev', 'stdio,id=ser0,mux=on,signal=off', '-mon', 'chardev=ser0']
		if opts.x86:
			return [*args, '-serial', 'chardev:ser0']
		return [*args, '-device', 'pci-serial,chardev=ser0', '-serial', 'none']

	return [
		*video,
		'-audiodev',
		f'{opts.audio},id=snd0',
		'-device',
		'ich9-intel-hda',
		'-device',
		'hda-duplex,audiodev=snd0',
		'-monitor',
		'stdio',
	]


def machine_args(opts: Opts) -> list[str]:
	if opts.x86:
		return ['-machine', 'q35', '-cpu', 'host', '-enable-kvm']
	if platform.machine() == 'aarch64':
		args = ['-machine', 'virt', '-cpu', 'host', '-enable-kvm']
	else:
		args = ['-machine', 'virt', '-cpu', 'max', '-accel', 'tcg,thread=multi']
	# virt has neither IDE nor PS/2: ISO on virtio-scsi, USB input
	return [*args, '-device', 'qemu-xhci', '-device', 'usb-kbd', '-device', 'usb-tablet']


def disk_args(opts: Opts, boot_order: str) -> list[str]:
	if opts.x86:
		# q35 has IDE for -cdrom and PS/2 input; -boot order is honored by both firmwares
		return ['-drive', f'file={opts.disk},format=qcow2,if=virtio', '-boot', f'order={boot_order}']
	# -boot order means nothing to edk2 on arm, bootindex does (fw_cfg), so
	# the disk yields to the cdrom whenever one is attached.
	disk_index = 1 if boot_order == 'd' else 0
	return [
		'-drive',
		f'file={opts.disk},format=qcow2,if=none,id=hd0',
		'-device',
		f'virtio-blk-pci,drive=hd0,bootindex={disk_index}',
		'-device',
		'virtio-scsi-pci,id=scsi0',
	]


def media_args(opts: Opts) -> list[str]:
	if opts.uki:
		return ['-kernel', str(opts.uki)]

	iso = require_iso(opts)
	if opts.x86:
		args = ['-cdrom', str(iso)]
	else:
		args = ['-drive', f'file={iso},media=cdrom,if=none,id=cd0,readonly=on', '-device', 'scsi-cd,drive=cd0,bootindex=0']
	if opts.serial != '0':
		cmdline = extract_iso_kernel(opts, iso)
		args += ['-kernel', str(BOOT_DIR / 'vmlinuz'), '-initrd', str(BOOT_DIR / 'initrd'), '-append', f'{cmdline} console=ttyS0,115200']
	return args


def run_foreground(cmd: list[str]) -> int:
	proc = subprocess.Popen(cmd)
	try:
		while True:
			try:
				return proc.wait()
			except KeyboardInterrupt:
				# ^C reaches qemu too (same process group): let it shut down
				continue
	finally:
		if sys.stdin.isatty():
			subprocess.run(['stty', 'sane'], check=False)


def tvm() -> None:
	parser = argparse.ArgumentParser(
		prog='python -m archinstoo --script dev.tvm',
		description=header(),
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	parser.add_argument('mode', nargs='?', default='default', choices=MODES, metavar='{default,keep,boot,clean,help}')
	args = parser.parse_args()
	mode = MODES[args.mode]

	opts = read_opts()

	if mode == 'help':
		parser.print_help()
		raise SystemExit(0)

	if mode == 'clean':
		clean(opts)
		raise SystemExit(0)

	attach_iso = mode != 'boot'
	boot_order = 'd' if attach_iso else 'c'

	check_host_deps(opts, attach_iso)
	ensure_no_running_vm()
	firmware = probe_ovmf(opts)

	if mode == 'boot':
		require_disk(opts)
	elif mode == 'keep':
		require_disk(opts)
		require_media(opts)
	else:
		require_media(opts)
		opts.disk.unlink(missing_ok=True)
		if rc := subprocess.run(['qemu-img', 'create', '-f', 'qcow2', str(opts.disk), opts.disk_size], check=False).returncode:
			error(f'qemu-img could not create {opts.disk}')
			raise SystemExit(rc)

	if firmware and not opts.ovmf_vars.exists():
		shutil.copy(firmware[1], opts.ovmf_vars)

	if opts.serial == '1':
		for path in (SERIAL, MONITOR, LOG, CAPTURE):
			path.unlink(missing_ok=True)
	if opts.gl:
		ensure_virgl(opts)

	cmd = [
		opts.qemu,
		*machine_args(opts),
		'-m',
		opts.ram,
		'-smp',
		opts.cpus,
		*disk_args(opts, boot_order),
		'-device',
		'virtio-net-pci,netdev=net0',
		'-netdev',
		'user,id=net0',
		*console_args(opts),
	]
	if firmware:
		cmd += ['-drive', f'if=pflash,format=raw,readonly=on,file={firmware[0]}', '-drive', f'if=pflash,format=raw,file={opts.ovmf_vars}']
	if attach_iso:
		cmd += media_args(opts)
	cmd += opts.extra

	# print the assembled command instead of running it, one arg per line
	if opts.dry:
		print('\n'.join(cmd))
		raise SystemExit(0)

	if opts.serial == '1':
		if rc := subprocess.run(cmd, check=False).returncode:
			raise SystemExit(rc)
		info(f'VM detached, pid {PIDFILE.read_text().strip()}')
		info('drive it interactively: ./RUN --script dev.tser attach (Ctrl-] detaches)')
		info("or sequenced: ./RUN --script dev.tser login && ./RUN --script dev.tser run 'ls /'")
		raise SystemExit(0)

	raise SystemExit(run_foreground(cmd))


tvm()
