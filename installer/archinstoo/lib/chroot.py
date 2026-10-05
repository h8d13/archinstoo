import shlex
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.general import SysCommand, run
from archinstoo.lib.linux_path import LPath
from archinstoo.lib.output import debug, info, warn
from archinstoo.lib.utils.env import Os

if TYPE_CHECKING:
	from subprocess import CompletedProcess

	from archinstoo.lib.installer import Installer

# running commands inside the mounted target; a target at / runs them on
# the host as is


def chroot_prefix(target: Path) -> list[str]:
	# -S goes through systemd-run: needs a booted systemd >= 257 outside any
	# chroot, which only an Arch host/ISO guarantees
	prefix = ['arch-chroot']
	if Os.running_from_arch() and Os.has_systemd():
		prefix.append('-S')
	prefix.append(str(target))
	return prefix


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
			cmd = ['su', '-', run_as, '-c', shlex.join(cmd)]
		argv = cmd if on_host else [*chroot_prefix(target), *cmd]
		return run(argv, env=env)  # env: secrets (NEWPIN) stay off argv and out of cmd_history

	if run_as:
		cmd = f'su - {run_as} -c {shlex.quote(cmd)}'
	if not on_host:
		cmd = f'{" ".join(chroot_prefix(target))} {cmd}'
	return SysCommand(cmd, peek_output=peek_output)


def drop_to_shell(target: Path) -> None:
	# inherit this console rather than run under SysCommand's pty: that one
	# captures output but never feeds our stdin back in, so the shell would
	# sit there taking no input
	proc = subprocess.run(['arch-chroot', str(target)], check=False)  # noqa: S603,S607 - fixed argv, arch-chroot from $PATH
	if proc.returncode:
		# non-zero is normal: it carries out whatever the user last ran
		debug(f'arch-chroot exited {proc.returncode}')


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
