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
	# the one $TERMINAL rides on. Guarded per key so a second writer (or a
	# re-run) does not stack duplicate lines.
	env_path = target / 'etc/environment'
	existing = env_path.read_text() if env_path.exists() else ''
	defined = {line.split('=', 1)[0] for line in existing.splitlines()}

	fresh = {k: v for k, v in env_vars.items() if k not in defined}
	if not fresh:
		debug(f'Env vars already defined, not overwriting: {sorted(env_vars)}')
		return

	env_path.write_text(existing + ''.join(f'{k}={v}\n' for k, v in fresh.items()))
	info(f'Wrote {", ".join(fresh)} to {env_path}')
