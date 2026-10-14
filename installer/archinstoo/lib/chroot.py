import shlex
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.general import SysCommand, run
from archinstoo.lib.linux_path import LPath
from archinstoo.lib.output import debug, info, warn

if TYPE_CHECKING:
	from subprocess import CompletedProcess

	from archinstoo.lib.installer import Installer

# running commands inside the mounted target; a target at / runs them on
# the host as is

# su - resets the environment; proxies set for the install must still reach
# git/curl in custom commands
KEEP_ENV = ('http_proxy', 'https_proxy', 'no_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY')


# arch-chroot's set, mounted once per target instead of per command. /run
# is the host's: udev's database there is what dracut's hostonly detection
# and grub2-probe resolve the root device through. teardown_layout's
# umount -R takes them down with the layout
_API_MOUNTS = (
	('proc', ['-t', 'proc', 'proc', '-o', 'nosuid,noexec,nodev']),
	# rslave: unmounting the target must not propagate back to the host's
	# /sys and /dev submounts
	('sys', ['--rbind', '--make-rslave', '/sys']),
	('dev', ['--rbind', '--make-rslave', '/dev']),
	('run', ['--bind', '--make-private', '/run']),
	('tmp', ['-t', 'tmpfs', 'tmp', '-o', 'mode=1777,strictatime,nodev,nosuid']),
)


def mount_api(target: Path) -> None:
	# idempotent: every chroot entry calls it, the first one mounts
	if target == Path('/'):
		return
	for name, args in _API_MOUNTS:
		path = target / name
		path.mkdir(exist_ok=True)
		if path.is_mount():
			continue
		debug(f'Mounting {name} at {path}')
		SysCommand(['mount', *args, str(path)])


def chroot_prefix(target: Path) -> list[str]:
	# plain chroot(1) inherits our environment (proxies)
	mount_api(target)
	return ['chroot', str(target)]


def su_prefix(run_as: str) -> list[str]:
	return ['su', '-w', ','.join(KEEP_ENV), '-', run_as, '-c']


def run_in_target(
	target: Path,
	cmd: str | list[str],
	run_as: str | None = None,
	peek_output: bool = False,
	env: dict[str, str] | None = None,
) -> SysCommand | CompletedProcess[bytes]:
	on_host = target == Path('/')

	# argv list form avoids shell injection when arguments come from user or config input
	if isinstance(cmd, list):
		if run_as:
			cmd = [*su_prefix(run_as), shlex.join(cmd)]
		argv = cmd if on_host else [*chroot_prefix(target), *cmd]
		return run(argv, env=env)  # env: secrets (NEWPIN) stay off argv and out of cmd_history

	if run_as:
		cmd = f'{shlex.join(su_prefix(run_as))} {shlex.quote(cmd)}'
	if not on_host:
		cmd = f'{shlex.join(chroot_prefix(target))} {cmd}'
	return SysCommand(cmd, peek_output=peek_output)


def drop_to_shell(target: Path) -> None:
	# inherit this console rather than run under SysCommand's pty: that one
	# captures output but never feeds our stdin back in, so the shell would
	# sit there taking no input
	proc = subprocess.run([*chroot_prefix(target), '/bin/bash'], check=False)  # noqa: S603 - fixed argv, chroot from $PATH
	if proc.returncode:
		# non-zero is normal: it carries out whatever the user last ran
		debug(f'chroot shell exited {proc.returncode}')


def chown_tree(installation: Installer, username: str, path: str) -> None:
	# installer writes into $HOME as root; hand the tree back before first login
	debug(f'chown -R {username}:{username} {path}')
	installation.arch_chroot(['chown', '-R', f'{username}:{username}', path])


def run_custom_user_commands(installation: Installer, commands: list[str]) -> None:
	for index, command in enumerate(commands):
		script_path = LPath(f'/var/tmp/user-command.{index}.sh')  # noqa: S108 - path inside install target, not host /tmp
		chroot_path = installation.target / script_path.relative_to_root()

		# Do not throw error instead warn
		info(f'Executing custom command "{command}" ...')
		chroot_path.write_text(command)

		try:
			installation.arch_chroot(f'bash {script_path}')
		except SysCallError as e:
			warn(f'Custom command "{command}" failed: {e}')
		finally:
			chroot_path.unlink()
