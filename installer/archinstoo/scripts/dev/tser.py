# Serial console driver for the headless dev VM (A2_SERIAL=1 ./RUN --script dev.tvm).
#
# QEMU exposes two unix sockets and two growing log files:
#   .dev-serial.sock    guest ttyS0 (write keystrokes here)
#   .dev-serial.log     everything the guest ever printed on ttyS0
#   .dev-capture.log    guest ttyS1, byte-exact (see 'capture' below)
#   .dev-monitor.sock   QEMU HMP monitor (sendkey, quit, info ...)
#
# Reads come from the log, not the socket: the log survives across
# invocations, so each command here is a short-lived connect/act/exit
# instead of an interactive session that has to stay attached.
#
# Usage (from the repo root, tser = ./RUN --script dev.tser):
#     tser attach                 interactive ttyS0 in this terminal, Ctrl-]
#                                 detaches (the VM keeps running). One
#                                 client at a time: other modes wait on it
#     tser read [-n LINES]        dump console output (default: last 50)
#     tser login                  log in as root, sane tty width
#     tser send TEXT              type TEXT + Enter on ttyS0
#     tser run CMD [-t SEC]       run CMD in the guest shell, print output,
#                                 exit with the guest's return code
#     tser capture CMD [-t SEC]   same, but via ttyS1: exact bytes, safe to
#                                 pipe into jq/diff
#     tser push SRC [DEST]        copy a host file or directory into the
#                                 guest over http (a directory arrives as a
#                                 tree, DEST defaults to /root/<name>)
#     tser ctrl KEY [KEY ...]     raw bytes on ttyS0: ctrl-<letter>, esc,
#                                 ret, tab, space, up/down/left/right.
#                                 Steers a curses menu, interrupts a
#                                 running script, ends a chrooted shell
#     tser keys KEY [KEY ...]     monitor sendkey (bootloader menus: up/ret)
#     tser type TEXT              TEXT + Enter as sendkeys: greeter or VT
#                                 login when the guest has no serial getty
#     tser mon CMD                raw HMP monitor command
#     tser status                 is the VM alive, how big is the log
#     tser quit                   kill the VM

# Example:
#     tser run 'pacman -Sy --noconfirm git'
#     tser run 'git clone --depth 1 <url>/archinstoo /root/archinstoo'
# craft a config, reference found in repo (credentials go in as crypt hashes)
#     tser send 'python3 -B -m archinstoo --script guided \
#       --config examples/vm_unattended.json --silent --advanced --debug'
# examples/vm_unattended.json ships root and user 'vm' both with password
# 'test' (yescrypt hashes in auth_config). After a guided install, boot the
# disk (A2_SERIAL=1 ./RUN --script dev.tvm boot) and log in straight away, no chpasswd needed:
#     tser login -p test           # root
#     tser login -u vm -p test     # user
#
# Foreign hosts for distros/: ./distros/CLOUD fed|deb boots a cloud image,
# then tser login -p test

import argparse
import os
import re
import select
import shutil
import socket
import sys
import tarfile
import tempfile
import termios
import threading
import time
import tty
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NoReturn

from archinstoo.lib.output import error, info
from archinstoo.scripts.dev._vm import CAPTURE, LOG, MONITOR, SERIAL, vm_pid

# terminal control noise: CSI from agetty, pacman progress bars, the
# installer TUI; DCS and OSC from systemd, which resets the tty (ESC[!p,
# OSC 104), tags it (OSC 3008 context) and asks the terminal its name
# (DCS +q) every time it spawns a getty. Nobody on the host end answers,
# so the queries stay in the log as bytes: printed raw they make the
# host terminal answer into the shell instead. Payloads stop at ESC/BEL
# so a truncated sequence at the tail of the log cannot swallow the rest
ANSI = re.compile(
	# busybox ash's prompt cursor query (ESC[6n), any byte doubled (see
	# fuzzy): a leftover 'n' hides the prompt from wait_idle
	r'\x1b+\[+6+n+'
	r'|\x1b\[[0-9;?<=>]*[ -/]*[@-~]'  # CSI: params, intermediates (ESC[!p), final
	r'|\x1bP[^\x1b\x07]*\x1b\\'  # DCS ... ST
	r'|\x1b[\]_^X][^\x1b\x07]*(?:\x07|\x1b\\)'  # OSC/APC/PM/SOS ... BEL or ST
	r'|\x1b[ -/]*[0-~]'  # two/three byte escapes: charset selects, ESC7/ESC8
)
# grml zsh pads the prompt line out to the tty width, 400 blanks of nothing
PROMPT = re.compile(r'#|\S+@\S+ .* #')
# a shell waiting for input ends the line with its prompt char: 'root@archiso
# ~ #' on the ISO, '[root@host ~]#' once installed
# grml appends ' :(' to the prompt after a nonzero exit
IDLE = re.compile(r'[#$](\s*:\()?$')


def fuzzy(text: str) -> str:
	# QEMU logs a chardev buffer before writing it, so bytes replayed after
	# a partial socket write land in the log twice ('Swap' -> 'Swaap').
	# Harmless in prose, fatal for an exact marker match, so let every
	# character of the marker repeat.
	return ''.join(re.escape(char) + '+' for char in text)


def log_size() -> int:
	try:
		return LOG.stat().st_size
	except FileNotFoundError:
		return 0


def log_read(offset: int = 0) -> bytes:
	try:
		with LOG.open('rb') as fh:
			fh.seek(offset)
			return fh.read()
	except FileNotFoundError as e:
		error(f'{LOG} missing, is the VM running? (A2_SERIAL=1 ./RUN --script dev.tvm)')
		raise SystemExit(1) from e


def clean(raw: bytes) -> str:
	# busybox ash (alpine) prefixes its cursor-position query with a bare ESC
	# ('\x1b\x1b[6n'), and one left on the end of the prompt line is enough to
	# make it stop looking like a prompt, so wait_idle never fires. Drop any
	# ESC the sequence patterns above did not consume
	# the tty's onlcr turns an explicit '\r\n' into '\r\r\n' (systemd status
	# lines, agetty), so runs of CR before LF are one line end, not blanks.
	# A lone CR is a redraw (pacman progress bars): keep it as a line break
	text = re.sub(r'\r+\n', '\n', raw.decode('utf-8', 'replace'))
	# readline rings BEL for the ^U serial_write sends on an empty line
	return ANSI.sub('', text).replace('\x1b', '').replace('\x07', '').replace('\r', '\n')


def paced_send(sock: socket.socket, payload: bytes) -> None:
	# Pace it. The emulated 16550 takes 16 bytes at a time, so a big
	# write is always partial, and QEMU's retry re-sends a byte it
	# already delivered ('git' arriving as 'gitt'). Small writes with a
	# gap keep the FIFO from ever being the thing that truncates us.
	for start in range(0, len(payload), 8):
		sock.sendall(payload[start : start + 8])
		time.sleep(0.015)


def serial_write(data: bytes, kill_line: bool = True) -> None:
	if not SERIAL.exists():
		error(f'{SERIAL} missing, is the VM running? (A2_SERIAL=1 ./RUN --script dev.tvm)')
		raise SystemExit(1)
	with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
		sock.connect(str(SERIAL))
		# ^U first: anything the guest left half-typed (zsh refusing to run
		# a missing binary, an aborted paste) would otherwise get this
		# command appended to it, and neither line would ever execute.
		# Raw keys skip it: ^U is itself input to whatever is reading.
		paced_send(sock, b'\x15' + data if kill_line else data)
		# chardev drops buffered input on hangup, let QEMU drain first
		time.sleep(0.2)


def monitor_cmd(cmd: str, timeout: float = 5.0) -> str:
	if not MONITOR.exists():
		error(f'{MONITOR} missing, is the VM running? (A2_SERIAL=1 ./RUN --script dev.tvm)')
		raise SystemExit(1)
	with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
		sock.settimeout(timeout)
		sock.connect(str(MONITOR))
		sock.sendall(cmd.encode() + b'\n')
		out = b''
		deadline = time.time() + timeout
		while time.time() < deadline:
			try:
				chunk = sock.recv(4096)
			except TimeoutError:
				break
			if not chunk:
				break
			out += chunk
			# the banner already ends in a prompt; the second one is
			# the command's, hanging up before it lands drops the command
			if out.count(b'(qemu)') >= 2:
				break
		return clean(out)


def wait_for(pattern: str, timeout: float, offset: int = 0) -> tuple[str, re.Match[str] | None]:
	rx = re.compile(pattern, re.MULTILINE)
	deadline = time.time() + timeout
	while True:
		text = clean(log_read(offset))
		match = rx.search(text)
		if match:
			return text, match
		if time.time() >= deadline:
			return text, None
		time.sleep(0.25)


# Ctrl-], telnet's escape: not a key any guest program wants
DETACH = b'\x1d'


def cmd_attach(_args: argparse.Namespace) -> None:
	if not SERIAL.exists():
		error(f'{SERIAL} missing, is the VM running? (A2_SERIAL=1 ./RUN --script dev.tvm)')
		raise SystemExit(1)
	if not sys.stdin.isatty():
		error('attach needs a terminal, use send/run when scripting')
		raise SystemExit(1)

	info('attached to ttyS0, Ctrl-] detaches (the VM keeps running)')
	fd = sys.stdin.fileno()
	saved = termios.tcgetattr(fd)
	detach = b''
	with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
		sock.connect(str(SERIAL))
		# raw: keys (^C, ^D, arrows) go to the guest, not to this process
		tty.setraw(fd)
		try:
			while True:
				ready, _, _ = select.select([fd, sock], [], [])
				if sock in ready:
					if not (data := sock.recv(4096)):
						break
					sys.stdout.buffer.write(data)
					sys.stdout.buffer.flush()
				if fd in ready:
					keys, detach, _ = os.read(fd, 1024).partition(DETACH)
					paced_send(sock, keys)
					if detach:
						break
		finally:
			termios.tcsetattr(fd, termios.TCSADRAIN, saved)
	# a raw-mode line never got its carriage return
	print()
	info('detached' if detach else 'VM closed the console')


def cmd_read(args: argparse.Namespace) -> None:
	text = clean(log_read())
	lines = text.splitlines()
	if args.lines > 0:
		lines = lines[-args.lines :]
	print('\n'.join(lines))


def cmd_send(args: argparse.Namespace) -> None:
	serial_write(args.text.encode() + b'\n')


def wait_idle(timeout: float) -> bool:
	# Typing while the guest is mid-command loses the leading bytes of the
	# new line ('systemctl' arrived as 'stemctl'), so wait for a prompt to
	# be the last thing on the console. An interrupted TSER leaves the guest
	# running: the VM is a daemon, it never noticed we walked away.
	deadline = time.time() + timeout
	while True:
		lines = [ln.rstrip() for ln in clean(log_read()).splitlines() if ln.strip()]
		if lines and IDLE.search(lines[-1]):
			return True
		if time.time() >= deadline:
			return False
		time.sleep(0.25)


def marked_run(cmd: str, timeout: float) -> tuple[str, int | None]:
	# marker carries the exit status back out of the guest; the log
	# offset makes it unique per invocation without needing state
	if not wait_idle(timeout):
		error(f'guest still busy after {timeout}s, see ./RUN --script dev.tser read')
		raise SystemExit(1)
	offset = log_size()
	marker = f'TSER{offset}'
	serial_write(f'{cmd}; echo {marker}rc=$?\n'.encode())
	# 'rc=$?' in the echoed command line can't match 'rc=<digits>'
	# same duplication can inflate a nonzero status ('1' -> '11'); zero
	# survives it ('00' is still 0), so pass/fail stays trustworthy
	text, match = wait_for(fuzzy(marker) + r'rc=(\d+)', timeout, offset)
	# the match lands while the shell is still writing what follows the
	# marker (systemd's OSC 3008 end tag, the next prompt): cut there, a
	# half-written sequence would otherwise leak through as text
	if match:
		text = text[: match.end()]
	# drop the shell's echo of what we typed and grml zsh's prompt padding
	body = [ln for ln in text.splitlines() if marker not in ln and not PROMPT.fullmatch(ln.rstrip())]
	return '\n'.join(body).strip(), (int(match.group(1)) if match else None)


def cmd_run(args: argparse.Namespace) -> NoReturn:
	body, rc = marked_run(args.cmd, args.timeout)
	print(body)
	if rc is None:
		error(f'timeout after {args.timeout}s running {args.cmd!r}')
		raise SystemExit(1)
	raise SystemExit(rc)


def cmd_capture(args: argparse.Namespace) -> NoReturn:
	# ttyS1 is a file chardev, so what the guest writes there lands on
	# disk verbatim: no socket, no partial-write replay, no dup bytes.
	# ttyS0 still carries the marker that says when the command finished.
	cap_offset = CAPTURE.stat().st_size if CAPTURE.exists() else 0
	offset = log_size()
	marker = f'TSER{offset}'
	# subshell, so a 'a; b; c' command redirects all of it and not just c
	serial_write(f'({args.cmd}) >/dev/ttyS1 2>&1; echo {marker}rc=$?\n'.encode())
	_, match = wait_for(fuzzy(marker) + r'rc=(\d+)', args.timeout, offset)
	with CAPTURE.open('rb') as fh:
		fh.seek(cap_offset)
		sys.stdout.write(fh.read().decode('utf-8', 'replace'))
	if not match:
		error(f'timeout after {args.timeout}s capturing {args.cmd!r}')
		raise SystemExit(1)
	raise SystemExit(int(match.group(1)))


def cmd_login(args: argparse.Namespace) -> None:
	# wait for agetty first: bytes sent before it opens ttyS0 are dropped,
	# which looks exactly like a hang. archiso root has no password, an
	# installed target does, hence --password.
	text, match = wait_for(r'login:', args.timeout)
	if not match:
		print('\n'.join(text.splitlines()[-10:]))
		error('no login prompt on ttyS0')
		raise SystemExit(1)
	offset = log_size()
	serial_write(args.user.encode() + b'\n')
	if args.password:
		_, match = wait_for(r'[Pp]assword:', args.timeout, offset)
		if not match:
			error('no password prompt')
			raise SystemExit(1)
		serial_write(args.password.encode() + b'\n')
	# bash/zsh announce the shell as user@host, busybox ash as 'host:~#', and
	# a guest that logs in without either is a guest we cannot drive anyway
	text, match = wait_for(rf'{args.user}@\S+|\S+:~\s*[#$]', args.timeout, offset)
	if not match:
		print('\n'.join(text.splitlines()[-10:]))
		error('no shell prompt after login')
		raise SystemExit(1)
	# ttyS0 defaults to 80 cols, which chops long command echoes into
	# garbage mid-token; widen so 'run' output stays parseable
	serial_write(b'stty cols 400 rows 100\n')
	# grml zsh ships 'correct' on: one mangled byte turns a command into an
	# interactive 'correct git to _git [nyae]?' prompt that eats the next
	# keystroke and wedges the session. Fail loudly instead.
	# Wait for the prompt in between: a TCG guest is still chewing on stty
	# when the next line lands and loses its tail ('unsetopt corre').
	if not wait_idle(args.timeout):
		error('no prompt after stty')
		raise SystemExit(1)
	serial_write(b'[ -n "$ZSH_VERSION" ] && unsetopt correct\n')
	if not wait_idle(args.timeout):
		error('no prompt after unsetopt')
		raise SystemExit(1)
	info('logged in as root')


def cmd_push(args: argparse.Namespace) -> None:
	# qemu's user networking maps the host's loopback to 10.0.2.2 in the
	# guest, so a server bound to 127.0.0.1 is reachable there and nowhere
	# else on the network. Beats typing a payload in over a 16550.
	src = Path(args.src).expanduser().resolve()
	if not src.exists():
		error(f'{src} does not exist')
		raise SystemExit(1)

	dest = args.dest or f'/root/{src.name}'

	with tempfile.TemporaryDirectory() as tmp:
		root = Path(tmp)

		if src.is_dir():
			name = f'{src.name}.tar.gz'
			with tarfile.open(root / name, 'w:gz') as tar:
				tar.add(src, arcname='.')
		else:
			name = src.name
			shutil.copy2(src, root / name)

		server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
		port = server.server_address[1]
		threading.Thread(target=server.serve_forever, daemon=True).start()

		url = f'http://10.0.2.2:{port}/{name}'
		fetch = f'mkdir -p {dest} && curl -sSf {url} | tar -xzf - -C {dest}' if src.is_dir() else f'curl -sSf -o {dest} {url}'

		try:
			body, rc = marked_run(fetch, args.timeout)
		finally:
			server.shutdown()

	if body:
		print(body)
	if rc is None:
		error(f'timeout after {args.timeout}s pushing {src}')
		raise SystemExit(1)
	if rc != 0:
		error(f'guest fetch failed (rc {rc}): {fetch}')
		raise SystemExit(1)
	info(f'{src} -> {dest}')


# ttyS0 carries these as bytes, and `send` cannot: it kills the line first
# and ends with a newline. A curses menu wants ESC and arrows, a running
# script wants ^C, a chrooted shell wants ^D.
RAW_KEYS = {
	'esc': b'\x1b',
	'ret': b'\r',
	'tab': b'\t',
	'space': b' ',
	'up': b'\x1b[A',
	'down': b'\x1b[B',
	'right': b'\x1b[C',
	'left': b'\x1b[D',
}


def raw_key(key: str) -> bytes:
	if raw := RAW_KEYS.get(key):
		return raw
	# ctrl-<letter> is that letter's position in the alphabet
	letter = key.removeprefix('ctrl-')
	if key.startswith('ctrl-') and len(letter) == 1 and letter.isalpha():
		return bytes([ord(letter.lower()) - ord('a') + 1])
	error(f'unknown key {key!r}: ctrl-<letter> or one of {", ".join(RAW_KEYS)}')
	raise SystemExit(1)


def cmd_ctrl(args: argparse.Namespace) -> None:
	for key in args.keys:
		serial_write(raw_key(key), kill_line=False)
		# whatever is reading has to act on it before the next one lands
		time.sleep(args.delay)


def cmd_keys(args: argparse.Namespace) -> None:
	for key in args.keys:
		print(monitor_cmd(f'sendkey {key}'), end='')


# sendkey names for the ASCII that shows up in logins and shell lines
SHIFTED = {
	'!': '1',
	'@': '2',
	'#': '3',
	'$': '4',
	'%': '5',
	'^': '6',
	'&': '7',
	'*': '8',
	'(': '9',
	')': '0',
	'_': 'minus',
	'+': 'equal',
	'~': 'grave_accent',
	':': 'semicolon',
	'"': 'apostrophe',
	'<': 'comma',
	'>': 'dot',
	'?': 'slash',
	'|': 'backslash',
	'{': 'bracket_left',
	'}': 'bracket_right',
}
PLAIN = {
	' ': 'spc',
	'-': 'minus',
	'=': 'equal',
	'.': 'dot',
	'/': 'slash',
	',': 'comma',
	';': 'semicolon',
	"'": 'apostrophe',
	'`': 'grave_accent',
	'\\': 'backslash',
	'[': 'bracket_left',
	']': 'bracket_right',
	'\n': 'ret',
	'\t': 'tab',
}


def keyname(char: str) -> str:
	if char.isascii() and char.isalnum():
		return f'shift-{char.lower()}' if char.isupper() else char
	if char in SHIFTED:
		return f'shift-{SHIFTED[char]}'
	if char in PLAIN:
		return PLAIN[char]
	error(f'no sendkey name for {char!r}')
	raise SystemExit(1)


def cmd_type(args: argparse.Namespace) -> None:
	for char in args.text + '\n':
		monitor_cmd(f'sendkey {keyname(char)}')
		# the guest's key repeat window; faster and consecutive letters merge
		time.sleep(0.05)


def cmd_mon(args: argparse.Namespace) -> None:
	print(monitor_cmd(' '.join(args.cmd)), end='')


def cmd_status(_args: argparse.Namespace) -> NoReturn:
	pid = vm_pid()
	print(f'vm:      {"running pid " + str(pid) if pid else "not running"}')
	print(f'serial:  {SERIAL} {"ok" if SERIAL.exists() else "missing"}')
	print(f'monitor: {MONITOR} {"ok" if MONITOR.exists() else "missing"}')
	print(f'log:     {LOG} {log_size()} bytes')
	raise SystemExit(0 if pid else 1)


def cmd_quit(_args: argparse.Namespace) -> None:
	if not vm_pid():
		info('not running')
		return
	monitor_cmd('quit', timeout=2.0)
	for _ in range(20):
		if not vm_pid():
			info('vm stopped')
			return
		time.sleep(0.25)
	error('vm still running, kill it by hand')
	raise SystemExit(1)


def tser() -> None:
	parser = argparse.ArgumentParser(
		prog='python -m archinstoo --script dev.tser',
		description='Serial console driver for the headless dev VM (A2_SERIAL=1 ./RUN --script dev.tvm)',
	)
	sub = parser.add_subparsers(dest='mode', required=True)

	sub.add_parser('attach').set_defaults(func=cmd_attach)

	p = sub.add_parser('read')
	p.add_argument('-n', '--lines', type=int, default=50)
	p.set_defaults(func=cmd_read)

	p = sub.add_parser('send')
	p.add_argument('text')
	p.set_defaults(func=cmd_send)

	p = sub.add_parser('run')
	p.add_argument('cmd')
	p.add_argument('-t', '--timeout', type=float, default=120)
	p.set_defaults(func=cmd_run)

	p = sub.add_parser('capture')
	p.add_argument('cmd')
	p.add_argument('-t', '--timeout', type=float, default=120)
	p.set_defaults(func=cmd_capture)

	p = sub.add_parser('login')
	p.add_argument('-u', '--user', default='root')
	p.add_argument('-p', '--password', default='')
	p.add_argument('-t', '--timeout', type=float, default=180)
	p.set_defaults(func=cmd_login)

	p = sub.add_parser('push')
	p.add_argument('src')
	p.add_argument('dest', nargs='?')
	p.add_argument('-t', '--timeout', type=float, default=300)
	p.set_defaults(func=cmd_push)

	p = sub.add_parser('ctrl')
	p.add_argument('keys', nargs='+')
	p.add_argument('-d', '--delay', type=float, default=0.5)
	p.set_defaults(func=cmd_ctrl)

	p = sub.add_parser('keys')
	p.add_argument('keys', nargs='+')
	p.set_defaults(func=cmd_keys)

	p = sub.add_parser('type')
	p.add_argument('text')
	p.set_defaults(func=cmd_type)

	p = sub.add_parser('mon')
	p.add_argument('cmd', nargs='+')
	p.set_defaults(func=cmd_mon)

	sub.add_parser('status').set_defaults(func=cmd_status)
	sub.add_parser('quit').set_defaults(func=cmd_quit)

	args = parser.parse_args()
	args.func(args)


tser()
