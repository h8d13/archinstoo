import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from archinstoo.lib.output import error, info
from archinstoo.lib.utils.env import Env
from archinstoo.scripts.dev._vm import CAPTURE, LOG, MONITOR, PIDFILE, ROOT, SERIAL, STATE, VM, vm_console, vm_pid

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


@dataclass(frozen=True)
class Opts:
	arch: str
	console: str
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


def read_opts(console: str | None = None) -> Opts:
	arch = Env.get_value('A2_ARCH', 'x86_64')
	if arch not in FIRMWARE:
		error(f'A2_ARCH={arch} unsupported (x86_64, aarch64)')
		raise SystemExit(1)

	# --console wins; A2_SERIAL is its env form for scripts (./CLOUD):
	# 'tty' is its own mode, anything else is a boolean like A2_BIOS/A2_GL
	if not console and Env.get_value('A2_SERIAL', '').strip().lower() == 'tty':
		console = 'tty'
	elif not console:
		console = 'serial' if Env.get_bool('A2_SERIAL') else 'window'

	return Opts(
		arch=arch,
		console=console,
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


def probe_ovmf(opts: Opts) -> tuple[Path, Path] | None:
	if opts.bios:
		return None
	pkg, pairs = FIRMWARE[opts.arch]
	for code, nvram in pairs:
		if Path(code).is_file() and Path(nvram).is_file():
			return Path(code), Path(nvram)
	error(f"UEFI firmware for {opts.arch} not found. Install '{pkg}' or similar on your distro.")
	raise SystemExit(1)


def serial_log_args() -> list[str]:
	# ttyS0 as chardev ser0: the socket dev.vm talks to, plus the log it reads.
	# The socket's own logfile= logs a chunk when a write to a busy or
	# hanging-up client fails, then again when the 16550 retries it: one
	# doubled byte per hiccup. A hub (QEMU >= 10.0) fans the output out
	# instead, and the log is a plain file chardev, which never takes a
	# short write.
	return [
		'-chardev',
		f'socket,id=sock0,path={SERIAL},server=on,wait=off',
		'-chardev',
		f'file,id=log0,path={LOG},append=on',
		'-chardev',
		'hub,id=ser0,chardevs.0=sock0,chardevs.1=log0',
	]


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
	if attach_iso and opts.console != 'window' and not opts.uki and not shutil.which('bsdtar'):
		error(f'--console {opts.console} needs bsdtar to read the ISO (install libarchive)')
		raise SystemExit(1)


def ensure_no_running_vm() -> None:
	if pid := vm_pid():
		error(f'VM already running (pid {pid}, --console {vm_console()}), stop it with {VM} quit')
		raise SystemExit(1)
	PIDFILE.unlink(missing_ok=True)
	STATE.unlink(missing_ok=True)


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
		error(f'Disk missing, start with {VM} fresh first')
		raise SystemExit(1)


def clean(opts: Opts) -> None:
	ensure_no_running_vm()
	for path in (opts.disk, opts.ovmf_vars, SERIAL, LOG, CAPTURE, MONITOR, STATE):
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
	elif opts.console != 'window':
		video = ['-display', 'none']
	elif opts.x86:
		video = ['-vga', opts.vga, '-display', opts.display]
	else:
		video = ['-device', opts.vga, '-display', opts.display]

	if opts.console == 'serial':
		# Headless and detached: the console is a unix socket plus a log, so
		# dev.vm can connect, act and exit instead of holding a session open.
		# Audio is dropped, no session to play into.
		# ttyS1 is a plain file chardev: guest output redirected to /dev/ttyS1
		# is a byte-exact transcript of one command (dev.vm capture). ttyS0
		# stays the interactive end.
		args = [*video, *serial_log_args(), '-chardev', f'file,id=cap0,path={CAPTURE}']
		if opts.x86:
			args += ['-serial', 'chardev:ser0', '-serial', 'chardev:cap0']
		else:
			# q35's ISA 16550s become one dual-port PCI 16550 on virt, so the
			# guest still sees ttyS0/ttyS1. The pl011 stays off the sockets: its
			# QEMU model stops taking input after ~280 bytes in one line.
			args += ['-device', 'pci-serial-2x,chardev1=ser0,chardev2=cap0', '-serial', 'none']
		return [*args, '-monitor', f'unix:{MONITOR},server=on,wait=off', '-daemonize']

	if opts.console == 'tty':
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
	if opts.console != 'window':
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


def start(mode: str, console: str | None) -> None:
	# mode: fresh (new disk + ISO), keep (disk + ISO) or boot (disk only)
	opts = read_opts(console)
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

	if opts.console == 'serial':
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
		# every console writes one, so status/quit see a window VM too
		'-pidfile',
		str(PIDFILE),
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

	STATE.write_text(f'{opts.console}\n')

	if opts.console == 'serial':
		if rc := subprocess.run(cmd, check=False).returncode:
			raise SystemExit(rc)
		info(f'VM detached, pid {PIDFILE.read_text().strip()}')
		info(f'drive it interactively: {VM} attach (Ctrl-] detaches)')
		info(f"or sequenced: {VM} login && {VM} run 'ls /'")
		raise SystemExit(0)

	if opts.console == 'tty':
		info('ttyS0 is this terminal: Ctrl-a x quits, Ctrl-a c toggles the QEMU monitor')
	else:
		info('VM in a window. (qemu) below is the monitor, not the guest: quit or Ctrl-C stops the VM')
	raise SystemExit(run_foreground(cmd))
