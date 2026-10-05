import pytest

import archinstoo
from archinstoo.lib.exceptions import SysCallError

_DEPS = ('pacman', 'git', 'xfsprogs')


@pytest.mark.parametrize(
	('output', 'expected'),
	[
		('git\nxfsprogs\n', ['git', 'xfsprogs']),
		# only names we asked about are installable, anything else is noise
		('warning: whatever\ngit\n', ['git']),
	],
)
def test_missing_deps_reports_unsatisfied(monkeypatch: pytest.MonkeyPatch, output: str, expected: list[str]) -> None:
	# pacman -T exits 127 and prints one unsatisfied dep per line
	def _run(args: str, **kw: object) -> None:
		raise SysCallError(f'pacman {args} exited with abnormal exit code [127]', 127, worker_log=output.encode())

	monkeypatch.setattr(archinstoo.Pacman, 'run', _run)

	assert archinstoo._missing_deps(_DEPS) == expected


def test_missing_deps_all_satisfied(monkeypatch: pytest.MonkeyPatch) -> None:
	# -T exits 0 and prints nothing: e.g. xfsprogs covered by a provides
	monkeypatch.setattr(archinstoo.Pacman, 'run', lambda args, **kw: None)

	assert archinstoo._missing_deps(_DEPS) == []
