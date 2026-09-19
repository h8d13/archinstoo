from typing import TYPE_CHECKING

from archinstoo.lib.output import debug, info

if TYPE_CHECKING:
	from pathlib import Path

# plain file writers under the target's /etc that no package owns


def write_hostname(target: Path, hostname: str) -> None:
	(target / 'etc/hostname').write_text(hostname + '\n')
	debug(f'Wrote hostname {hostname}')


def write_environment(target: Path, env_vars: dict[str, str]) -> None:
	# pam_env exports /etc/environment into the session, graphical ones
	# included, which is the only path Wayland has for XKB_DEFAULT_* and
	# the one $TERMINAL rides on. Callers own the keys they hand over, so a
	# key already in the file is rewritten where it stands: a second pass
	# over a live target (its own /etc) must neither stack a duplicate line
	# nor leave the old value winning. Lines nobody claims stay untouched.
	if not env_vars:
		return

	env_path = target / 'etc/environment'
	lines = env_path.read_text().splitlines() if env_path.exists() else []

	pending = dict(env_vars)
	kept = []
	for line in lines:
		key = line.split('=', 1)[0]
		kept.append(f'{key}={pending.pop(key)}' if key in pending else line)

	kept += [f'{k}={v}' for k, v in pending.items()]

	env_path.write_text('\n'.join(kept) + '\n')
	info(f'Wrote {", ".join(env_vars)} to {env_path}')
