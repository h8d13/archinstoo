# vm cloud: a distro cloud image as the booted host, for --script bootstrap
# (and the native distros/ ports) from a real non-Arch system.
#
# The cloud image, as a throwaway overlay, is the boot disk (/dev/vda) and an
# empty disk rides along as the install target (/dev/vdb, see
# installer/examples/vm_cloud_bios.json). SeaBIOS, so the target installs grub
# on MBR. cloud-init takes its config (root password) off the SMBIOS serial,
# from a seed served here for as long as it reads it.

import dataclasses
import json
import shutil
import subprocess
import tempfile
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple

from archinstoo.lib.exceptions import FetchError
from archinstoo.lib.output import error, info
from archinstoo.lib.utils.env import Env
from archinstoo.lib.utils.net import download_file_from_url
from archinstoo.scripts.dev._drive import wait_for
from archinstoo.scripts.dev._launch import TARGET, Opts, ensure_no_running_vm, launch, read_opts
from archinstoo.scripts.dev._vm import ROOT, VM

CLOUD_DIR = ROOT / '.dev-cloud'
# cloud-init prints its summary line on the console once every stage ran
FINISHED = r'Cloud-init v\. .* finished'
FINISH_TIMEOUT = 600


class Image(NamedTuple):
	name: str
	url: str


def image(distro: str) -> Image:
	if distro == 'fed':
		rel = Env.get_value('A2_CLOUD_REL', '44')
		build = Env.get_value('A2_CLOUD_BUILD', '1.7')
		name = f'Fedora-Cloud-Base-Generic-{rel}-{build}.x86_64.qcow2'
		return Image(name, f'https://download.fedoraproject.org/pub/fedora/linux/releases/{rel}/Cloud/x86_64/images/{name}')
	name = 'debian-13-genericcloud-amd64.qcow2'
	return Image(name, f'https://cloud.debian.org/images/cloud/trixie/latest/{name}')


def fetch(img: Image) -> Path:
	# cached across runs, like the ISOs: every boot gets a fresh overlay
	CLOUD_DIR.mkdir(exist_ok=True)
	dest = CLOUD_DIR / img.name
	if dest.is_file() and dest.stat().st_size:
		return dest
	part = dest.with_name(f'{dest.name}.part')
	info(f'fetching {img.url}')
	try:
		download_file_from_url(img.url, part, timeout=60)
	except FetchError as err:
		error(str(err))
		raise SystemExit(1) from err
	part.rename(dest)
	return dest


def qemu_img(*args: str) -> None:
	if rc := subprocess.run(['qemu-img', *args], check=False).returncode:
		error(f'qemu-img {args[0]} failed')
		raise SystemExit(rc)


def write_seed(seed: Path, distro: str, password: str, user_data: Path | None) -> None:
	# vendor-data/network-config must exist: cloud-init retries 404s ~1/s for
	# ~20s each, which shows as "stuck" at cloud-init-network.service.
	# instance-id changes per run, else a reused overlay skips the seed
	(seed / 'vendor-data').write_text('')
	(seed / 'network-config').write_text('')
	(seed / 'meta-data').write_text(f'instance-id: cloud-{distro}-{int(time.time())}\nlocal-hostname: cloud-{distro}\n')
	# a given user-data goes in as is: users, keys, packages are its business
	if user_data:
		shutil.copy(user_data, seed / 'user-data')
		return
	# JSON is YAML: no indentation to keep straight against the code's tabs
	config = {
		'disable_root': False,
		'chpasswd': {'expire': False, 'users': [{'name': 'root', 'password': password, 'type': 'text'}]},
		'users': ['default', {'name': 'root'}],
	}
	(seed / 'user-data').write_text('\n'.join(('#cloud-config', json.dumps(config), '')))


def boot(distro: str, console: str | None, user_data: str | None) -> None:
	ensure_no_running_vm()
	password = Env.get_value('A2_CLOUD_PASS', 'test')
	# ./RUN cds into installer/, so a relative path means the repo root
	given = (ROOT / Path(user_data).expanduser()).resolve() if user_data else None
	if given and not given.is_file():
		error(f'--user-data {given} not found')
		raise SystemExit(1)
	opts = cloud_opts(console)
	backing = fetch(image(distro))

	# pristine every run: an overlay over the cached image, and an empty target
	opts.disk.unlink(missing_ok=True)
	TARGET.unlink(missing_ok=True)
	qemu_img('create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(backing), str(opts.disk), '20G')
	qemu_img('create', '-f', 'qcow2', str(TARGET), opts.disk_size)

	with tempfile.TemporaryDirectory(prefix='a2-seed-') as tmp:
		write_seed(Path(tmp), distro, password, given)
		# user-mode net: the guest reaches the host's loopback as 10.0.2.2
		server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=tmp))
		threading.Thread(target=server.serve_forever, daemon=True).start()
		seed_url = f'http://10.0.2.2:{server.server_address[1]}/'
		extra = ('-drive', f'file={TARGET},format=qcow2,if=virtio', '-smbios', f'type=1,serial=ds=nocloud;s={seed_url}')
		try:
			rc = launch(dataclasses.replace(opts, extra=(*opts.extra, *extra)), 'boot')
			# window/tty: launch held the terminal until the VM exited
			if rc or opts.dry or opts.console != 'serial':
				raise SystemExit(rc)
			_, done = wait_for(FINISHED, FINISH_TIMEOUT)
		finally:
			server.shutdown()

	if not done:
		error(f'cloud-init not done after {FINISH_TIMEOUT}s, see {VM} read')
		raise SystemExit(1)
	if given:
		info(f'cloud-init done: log in as {given.name} set up (target disk is /dev/vdb)')
	else:
		info(f'cloud-init done: {VM} login -p {password} (target disk is /dev/vdb)')


def boot_target(console: str | None) -> None:
	ensure_no_running_vm()
	opts = cloud_opts(console)
	if not (TARGET.is_file() and TARGET.stat().st_size):
		error(f'no {TARGET}, run {VM} cloud fed|deb and install onto /dev/vdb first')
		raise SystemExit(1)
	# fstab and grub name UUIDs, so vdb booting as vda comes up the same
	shutil.move(TARGET, opts.disk)
	raise SystemExit(launch(opts, 'boot'))


def cloud_opts(console: str | None) -> Opts:
	# serial unless asked otherwise: waiting on cloud-init reads its log.
	# SeaBIOS, the target installs grub on MBR
	if not console and not Env.has_value('A2_SERIAL'):
		console = 'serial'
	return dataclasses.replace(read_opts(console), bios=True)


def start(which: str, console: str | None, user_data: str | None) -> None:
	if which == 'target':
		boot_target(console)
	else:
		boot(which, console, user_data)
