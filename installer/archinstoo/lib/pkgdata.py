# Package-data helpers shared by the installer and the nvchecker tooling.
#
# _resolve.py (count/size scripts) imports this normally; nvchecker/NVGEN loads
# it by path, so this module MUST stay stdlib-only and free of intra-package
# imports. That constraint is the whole point: NVGEN runs on a checkout without
# the installer's runtime dependencies, and duplicating these two helpers there
# is what previously let them drift (a schema loader with its own regex, and a
# group expansion that read disabled repos).

import json
import re
import subprocess
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
	from pathlib import Path

# `// comment` on its own line, or trailing one that follows a comma. anything
# else (a comment after `]` with no comma) is left in place and surfaces as a
# JSONDecodeError rather than silently eating a line
_COMMENT_RE = re.compile(r'(?m)^\s*//.*$|(?<=,)\s*//.*$')


def load_jsonc(path: Path) -> dict[str, Any]:
	# strip // comments, then parse as json
	text = _COMMENT_RE.sub('', path.read_text())
	result: dict[str, Any] = json.loads(text)
	return result


def parse_groups(text: str) -> dict[str, set[str]]:
	# `pacman -Sgg` output: one `<group> <member>` pair per line
	groups: dict[str, set[str]] = {}
	for line in text.splitlines():
		parts = line.split()
		if len(parts) == 2:
			groups.setdefault(parts[0], set()).add(parts[1])
	return groups


def sync_groups() -> dict[str, set[str]]:
	# group -> members, from one `pacman -Sgg`. going through pacman rather than
	# reading /var/lib/pacman/sync/*.db ourselves means the repos enabled in
	# pacman.conf and a custom DBPath are honoured for free: a disabled-but-
	# present db (core-testing, a local repo) would otherwise contribute members
	# pacman would never install.
	proc = subprocess.run(['pacman', '-Sgg'], capture_output=True, text=True, check=False)  # noqa: S607 - pacman from $PATH
	if proc.returncode != 0:
		return {}
	return parse_groups(proc.stdout)


def expand_groups(pkgs: set[str]) -> set[str]:
	# Several schema entries (mate, xfce4, xfce4-goodies, lxqt, deepin, cosmic,
	# budgie) are pacman GROUPS, which pacstrap installs as their members but
	# pactree and expac both report as unknown. Left unexpanded a group resolves
	# to nothing, so its members and their whole dependency closure drop out of
	# the estimates silently. Names that aren't groups pass through untouched.
	groups = sync_groups()
	expanded: set[str] = set()
	for pkg in pkgs:
		expanded.update(groups.get(pkg, {pkg}))
	return expanded
