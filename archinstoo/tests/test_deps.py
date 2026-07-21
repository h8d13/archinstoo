import pytest

import archinstoo
from archinstoo.lib.exceptions import SysCallError

_DEPS = ('pacman', 'git', 'ntfsprogs')


@pytest.mark.parametrize(
	('output', 'expected'),
	[
		('git\nntfsprogs\n', ['git', 'ntfsprogs']),
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
	# -T exits 0 and prints nothing: e.g. ntfsprogs covered by a provides
	monkeypatch.setattr(archinstoo.Pacman, 'run', lambda args, **kw: None)

	assert archinstoo._missing_deps(_DEPS) == []
