# pacman group membership.
#
# Unlike its siblings here this module talks to pacman through plain subprocess
# and imports nothing from the package: nvchecker/NVGEN loads it BY PATH so the
# tooling and the count/size scripts expand groups identically. Adding an
# `archinstoo.lib` import breaks that load (tests/test_schema_drift.py pins it).

import subprocess


def parse(text: str) -> dict[str, set[str]]:
	# `pacman -Sgg` output: one `<group> <member>` pair per line
	groups: dict[str, set[str]] = {}
	for line in text.splitlines():
		parts = line.split()
		if len(parts) == 2:
			groups.setdefault(parts[0], set()).add(parts[1])
	return groups


def sync() -> dict[str, set[str]]:
	# group -> members, from one `pacman -Sgg`. going through pacman rather than
	# reading /var/lib/pacman/sync/*.db ourselves means the repos enabled in
	# pacman.conf and a custom DBPath are honoured for free: a disabled-but-
	# present db (core-testing, a local repo) would otherwise contribute members
	# pacman would never install.
	proc = subprocess.run(['pacman', '-Sgg'], capture_output=True, text=True, check=False)  # noqa: S607 - pacman from $PATH
	if proc.returncode != 0:
		return {}
	return parse(proc.stdout)


def expand(pkgs: set[str]) -> set[str]:
	# Several schema entries (mate, xfce4, xfce4-goodies, lxqt, deepin, cosmic,
	# budgie) are pacman GROUPS, which pacstrap installs as their members but
	# pactree and expac both report as unknown. Left unexpanded a group resolves
	# to nothing, so its members and their whole dependency closure drop out of
	# the estimates silently. Names that aren't groups pass through untouched.
	groups = sync()
	expanded: set[str] = set()
	for pkg in pkgs:
		expanded.update(groups.get(pkg, {pkg}))
	return expanded
