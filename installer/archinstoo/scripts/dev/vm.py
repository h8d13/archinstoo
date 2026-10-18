# Dev test VM for archinstoo: boots an ISO or the installed disk under QEMU,
# and drives it over serial. One VM at a time, all state in the repo root.
# ISO building is intentionally NOT done here, use isos/ISOMOD for that/default Arch ISO.
# Credits to @Softer, modified for archinstoo.
#
# Host deps:
#   sudo pacman -S --needed qemu-base qemu-ui-gtk qemu-audio-pipewire edk2-ovmf
#   (QEMU >= 10.0: --console serial builds its console on the chardev hub)
#   (swap qemu-ui-gtk for qemu-ui-sdl/qemu-ui-curses if you prefer; set A2_DISPLAY_BACKEND to match)
#   (audio backend is a separate pkg: qemu-audio-pipewire (default), qemu-audio-pa, qemu-audio-alsa; set A2_AUDIO_BACKEND to match)
#   (A2_ARCH=aarch64 adds: qemu-system-aarch64 edk2-aarch64; qemu-hw-display-virtio-gpu{,-pci} for A2_VGA=virtio-gpu-pci)
#   bsdtar (libarchive) to boot an ISO with --console serial or tty
#
# Usage (from the repo root, vm = ./RUN --script dev.vm):
#   Start, --console picks how you reach the guest (default window):
#     vm fresh [--console C]    new disk, boot ISO
#     vm keep  [--console C]    reuse disk, boot ISO              (alias k)
#     vm boot  [--console C]    boot the installed disk, no ISO   (alias b)
#     vm cloud fed|deb [--console C] [--user-data FILE]
#                               a distro cloud image as the host (overlay on
#                               vda, empty install target on vdb), SeaBIOS,
#                               waits for cloud-init (default serial).
#                               --user-data: cloud-init config served as is,
#                               else root gets A2_CLOUD_PASS
#     vm cloud target [--console C]
#                               boot what got installed on vdb (the overlay
#                               is dropped, the target becomes vda)
#     vm clean                  remove disk, NVRAM, target and logs, ISOs and
#                               cloud images untouched (alias c)
#   Consoles:
#     window   graphical window; (qemu) in this terminal is the QEMU monitor,
#              not the guest: 'quit' there or Ctrl-C stops the VM
#     serial   headless and detached, no window: drive it with the commands
#              below. ISO modes direct-boot the ISO's own kernel via -kernel
#              so console=ttyS0 can be forced; OVMF still boots it EFI-stub,
#              so the guest keeps a real UEFI environment. 'boot' has no such
#              hook: the installed system only talks to ttyS0 if its own
#              cmdline says console=ttyS0. With A2_GL=1 the virgl window stays
#              too: a real session on screen while serial drives the greeter
#              (type/keys) and mon takes screendumps.
#     tty      same boot as serial, but ttyS0 is this terminal, in the
#              foreground: Ctrl-a x quits, Ctrl-a c toggles the QEMU monitor
#   Drive a --console serial VM:
#     vm attach                 interactive ttyS0 in this terminal, Ctrl-]
#                               detaches (the VM keeps running). One client
#                               at a time: the commands below wait on it
#     vm login [-u U] [-p P]    log in (root by default), sane tty width
#     vm send TEXT              type TEXT + Enter on ttyS0
#     vm run CMD [-t SEC]       run CMD in the guest shell, print output,
#                               exit with the guest's return code
#     vm capture CMD [-t SEC]   same, but via ttyS1: the command's raw output
#                               alone, safe to pipe into jq/diff
#     vm push SRC [DEST]        copy a host file or directory into the guest
#                               over http (a directory arrives as a tree,
#                               DEST defaults to /root/<name>)
#     vm read [-n LINES]        dump console output (default: last 50)
#     vm ctrl KEY [KEY ...]     raw bytes on ttyS0: ctrl-<letter>, esc, ret,
#                               tab, space, up/down/left/right. Steers a curses
#                               menu, interrupts a running script, ends a
#                               chrooted shell
#     vm keys KEY [KEY ...]     monitor sendkey (bootloader menus: up/ret)
#     vm type TEXT              TEXT + Enter as sendkeys: greeter or VT login
#                               when the guest has no serial getty
#     vm mon CMD                raw HMP monitor command
#   Any console:
#     vm status                 is a VM alive, which console, how big the log
#     vm quit                   stop the VM
#
# Example, an unattended install from this checkout:
#     vm fresh --console serial
#     vm login
#     vm push installer /root/archinstoo
#     vm run 'cd /root/archinstoo && python3 -B -m archinstoo --script guided \
#       --config examples/vm_unattended.json --silent --advanced' -t 3600
#     vm quit && vm boot --console serial
#     vm login -p test           # root; 'vm login -u vm -p test' for the user
# examples/vm_unattended.json ships root and user 'vm' both with password
# 'test' (yescrypt hashes in auth_config), no chpasswd needed.
# A foreign host for --script bootstrap (or the distros/ ports). fed: the
# bootstrap wants python >= 3.14 on the host, debian 13 ships 3.13:
#     vm cloud fed --user-data installer/examples/cloud_user_data.yaml
#     vm login -p test && vm push installer
#     vm run 'cd /root/installer && python3 -B -m archinstoo --script \
#       bootstrap -- --script guided --config examples/vm_cloud_bios.json \
#       --silent' -t 3600
#     vm quit && vm cloud target
#
# Host artifacts (created in repo root, git-ignored):
#   .dev-disk.qcow2     VM disk image (qemu-img), the overlay under vm cloud
#   .dev-target.qcow2   vm cloud's install target (vdb)
#   .dev-cloud/         cached cloud images
#   .dev-ovmf-vars.fd   persistent UEFI NVRAM (copied from OVMF_VARS)
#                       (both get a -<arch> suffix when A2_ARCH is not x86_64,
#                       so an aarch64 install never clobbers the x86_64 one)
#   .dev-vm.pid         the running VM, .dev-vm.state the --console it got
#   --console serial only:
#   .dev-boot/          kernel + initramfs pulled out of the ISO
#   .dev-serial.sock    guest ttyS0 (keystrokes go here)
#   .dev-serial.log     everything the guest ever printed on ttyS0
#   .dev-capture.log    guest ttyS1, what 'capture' reads back
#   .dev-monitor.sock   QEMU HMP monitor (sendkey, quit, info ...)
#   Reads come from the log, not the socket: the log survives across
#   invocations, so each command is a short-lived connect/act/exit instead of
#   a session that has to stay attached.
#
# Env overrides (on/off ones take 1/yes/true/on, anything else is off):
#   A2_SERIAL           default for --console: on = serial, 'tty' = tty
#   A2_ARCH             guest architecture: 'x86_64' (default) or 'aarch64'.
#                       aarch64 boots -machine virt with edk2-aarch64 pflash,
#                       KVM only when the host is aarch64 too (TCG -cpu max
#                       otherwise: slow, expect minutes to a shell). ISO
#                       discovery filters on the arch in the filename. No
#                       -cdrom on virt: the ISO rides virtio-scsi, boot order
#                       goes through bootindex. Input is USB (xhci kbd+tablet).
#                       Serial extracts the kernel the same way (arch/boot/aarch64/).
#                       virt's own UART is a pl011 whose QEMU model stalls on
#                       typed input past a few hundred bytes, so both lines
#                       ride a dual-port PCI 16550 instead: ttyS0/ttyS1 in
#                       the guest, same as q35, same sockets on the host.
#                       A2_BIOS and A2_UKI are x86_64 only.
#   A2_BIOS             on boots SeaBIOS instead of OVMF: no pflash, no
#                       NVRAM. The installed disk must carry a BIOS-capable
#                       bootloader (grub with a bios_grub partition).
#   A2_DEV_ISO          explicit ISO path (skips discovery)
#   A2_UKI              path to a live UKI (isos/UKIMOD output, isos/a/archinstoo.efi).
#                       Boots it via -kernel in place of an ISO: no cdrom, no
#                       kernel extraction, its baked cmdline already has ttyS0.
#                       Disk handling per mode is unchanged. OVMF only.
#                       Relative paths here and in push mean the repo root.
#   A2_RAM, A2_CPUS     VM resources (default 4G, 4)
#   A2_DISK_SIZE        new disk size (default 64G)
#   A2_DISPLAY_BACKEND  qemu -display value (default 'gtk,zoom-to-fit=off')
#   A2_VGA              qemu -vga value (default 'std'; 'virtio' needs qemu-hw-display-virtio-vga)
#                       On aarch64 it is a -device name instead (default 'ramfb',
#                       built in; 'virtio-gpu-pci' needs qemu-hw-display-virtio-gpu{,-pci})
#   A2_GL               on swaps video for virtio-vga-gl + display gl=on (virgl 3D accel).
#                       Overrides A2_VGA. niri/DMS have no software fallback, black-screen
#                       without this. Needs the full module chain (vga-gl alone won't load):
#                       qemu-hw-display-virtio-{gpu,gpu-gl,vga,vga-gl} + qemu-ui-opengl
#                       (aarch64: virtio-gpu-gl-pci, qemu-hw-display-virtio-gpu{,-gl,-pci,-gl-pci})
#   A2_QEMU_EXTRA       raw qemu args appended last (word-split, no quoting inside)
#   A2_CLOUD_REL, A2_CLOUD_BUILD
#                       vm cloud fed's release and compose (default 44, 1.7)
#   A2_CLOUD_PASS       root password cloud-init sets (default 'test')
#   A2_DRY              on prints the assembled qemu command and exits (still
#                       creates the disk/NVRAM the mode asks for)
#   A2_AUDIO_BACKEND    qemu -audiodev value (default 'pipewire'; 'pa'/'alsa' need the matching qemu-audio-* pkg)

import argparse
from pathlib import Path

from archinstoo.lib.cli import script_help
from archinstoo.scripts.dev import _cloud as cloud
from archinstoo.scripts.dev import _drive as drive
from archinstoo.scripts.dev import _launch as launch
from archinstoo.scripts.dev._vm import CONSOLES, need_serial


def vm() -> None:
	parser = argparse.ArgumentParser(
		prog='python -m archinstoo --script dev.vm',
		description=script_help(Path(__file__)),
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	sub = parser.add_subparsers(dest='command', required=True, metavar='COMMAND')

	# start
	console = argparse.ArgumentParser(add_help=False)
	console.add_argument('--console', choices=CONSOLES, help='how to reach the guest (default: window, or A2_SERIAL)')
	for mode, aliases in (('fresh', []), ('keep', ['k']), ('boot', ['b'])):
		p = sub.add_parser(mode, aliases=aliases, parents=[console])
		p.set_defaults(func=lambda args, mode=mode: launch.start(mode, args.console))
	p = sub.add_parser('cloud', parents=[console])
	p.add_argument('which', choices=('fed', 'deb', 'target'))
	p.add_argument('--user-data', metavar='FILE', help='cloud-init user-data served as is (default: root with A2_CLOUD_PASS)')
	p.set_defaults(func=lambda args: cloud.start(args.which, args.console, args.user_data))
	sub.add_parser('clean', aliases=['c']).set_defaults(func=lambda _args: launch.clean(launch.read_opts()))

	# drive a --console serial VM
	sub.add_parser('attach').set_defaults(func=drive.cmd_attach, serial=True)

	p = sub.add_parser('login')
	p.add_argument('-u', '--user', default='root')
	p.add_argument('-p', '--password', default='')
	p.add_argument('-t', '--timeout', type=float, default=180)
	p.set_defaults(func=drive.cmd_login, serial=True)

	p = sub.add_parser('send')
	p.add_argument('text')
	p.set_defaults(func=drive.cmd_send, serial=True)

	p = sub.add_parser('run')
	p.add_argument('cmd')
	p.add_argument('-t', '--timeout', type=float, default=120)
	p.set_defaults(func=drive.cmd_run, serial=True)

	p = sub.add_parser('capture')
	p.add_argument('cmd')
	p.add_argument('-t', '--timeout', type=float, default=120)
	p.set_defaults(func=drive.cmd_capture, serial=True)

	p = sub.add_parser('push')
	p.add_argument('src')
	p.add_argument('dest', nargs='?')
	p.add_argument('-t', '--timeout', type=float, default=300)
	p.set_defaults(func=drive.cmd_push, serial=True)

	p = sub.add_parser('read')
	p.add_argument('-n', '--lines', type=int, default=50)
	p.set_defaults(func=drive.cmd_read)

	p = sub.add_parser('ctrl')
	p.add_argument('keys', nargs='+')
	p.add_argument('-d', '--delay', type=float, default=0.5)
	p.set_defaults(func=drive.cmd_ctrl, serial=True)

	p = sub.add_parser('keys')
	p.add_argument('keys', nargs='+')
	p.set_defaults(func=drive.cmd_keys, serial=True)

	p = sub.add_parser('type')
	p.add_argument('text')
	p.set_defaults(func=drive.cmd_type, serial=True)

	p = sub.add_parser('mon')
	p.add_argument('cmd', nargs='+')
	p.set_defaults(func=drive.cmd_mon, serial=True)

	# any console
	sub.add_parser('status').set_defaults(func=drive.cmd_status)
	sub.add_parser('quit').set_defaults(func=drive.cmd_quit)
	sub.add_parser('help', aliases=['h']).set_defaults(func=lambda _args: parser.print_help())

	args = parser.parse_args()
	# say why a window/tty VM can't be driven before a command trips over it
	if getattr(args, 'serial', False):
		need_serial()
	args.func(args)


vm()
