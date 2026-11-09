# Classification of pacman and pacstrap failures.
# No I/O, so it is tested against recorded pacman output. classify() never
# raises: anything it does not recognise comes back as UNKNOWN, which the
# caller can still offer a generic retry for.

import re
from dataclasses import dataclass
from enum import StrEnum, auto

_CONFLICT = re.compile(r'(?P<pkg_a>\S+) and (?P<pkg_b>\S+) are in conflict')
_MISSING_TARGET = re.compile(r'target not found:\s*(?P<pkg>\S+)')
_FILE_EXISTS = re.compile(r'(?P<pkg>[\w@.+-]+):\s+(?P<path>/\S+) exists in filesystem')
_UNSATISFIED = re.compile(
	r"unable to satisfy dependency '(?P<dep>[^']+)' "
	r"required by '?(?P<pkg>[^'\s]+)'?"
)
_ERROR_LINE = re.compile(r'^error:\s*(?P<message>.+)$')

# package names may contain dots, so only strip the punctuation pacman adds
# around them when it builds a sentence
_TRAILING = '.,;:?!)\'"'

# file conflicts can list hundreds of paths, the prompt shows the first few
_SHOWN_PATHS = 5


class FailureKind(StrEnum):
	CONFLICT = auto()  # two packages cannot be installed together
	FILE_EXISTS = auto()  # files already on the target
	MISSING_TARGET = auto()  # no configured repository has it
	UNSATISFIED_DEPENDENCY = auto()  # nothing provides a dependency
	UNKNOWN = auto()  # anything else: download, signature, db errors


@dataclass(frozen=True)
class Failure:
	kind: FailureKind
	# packages involved, in the order pacman named them
	candidates: tuple[str, ...] = ()
	# conflicting files, only set for FILE_EXISTS
	paths: tuple[str, ...] = ()
	# the offending output, verbatim, for display
	summary: str = ''


def classify(output: str) -> Failure:
	lines = [line.strip() for line in output.splitlines() if line.strip()]

	for detect in (_conflict, _file_conflict, _missing_target, _unsatisfied):
		if failure := detect(lines):
			return failure

	return Failure(FailureKind.UNKNOWN, summary=_last_error(lines))


def strip_version(name: str) -> str:
	# 'foo>=2:1.2-3' -> 'foo'. Only constraints go: a trailing version is
	# part of names such as dotnet-runtime-8.0
	return re.split(r'[<>=]', name, maxsplit=1)[0].strip()


def _conflict(lines: list[str]) -> Failure | None:
	for line in lines:
		if match := _CONFLICT.search(line):
			pkg_a, pkg_b = _clean(match['pkg_a']), _clean(match['pkg_b'])
			if pkg_a and pkg_b:
				return Failure(
					FailureKind.CONFLICT,
					(pkg_a, pkg_b),
					summary=line,
				)
	return None


def _file_conflict(lines: list[str]) -> Failure | None:
	packages: list[str] = []
	paths: list[str] = []

	for line in lines:
		if match := _FILE_EXISTS.search(line):
			if (pkg := _clean(match['pkg'])) and pkg not in packages:
				packages.append(pkg)
			paths.append(match['path'])

	if not packages:
		return None

	summary = '\n'.join(paths[:_SHOWN_PATHS])
	if len(paths) > _SHOWN_PATHS:
		summary += f'\n... and {len(paths) - _SHOWN_PATHS} more file(s)'

	return Failure(FailureKind.FILE_EXISTS, tuple(packages), tuple(paths), summary)


def _missing_target(lines: list[str]) -> Failure | None:
	for line in lines:
		match = _MISSING_TARGET.search(line)
		if match and (pkg := _clean(match['pkg'])):
			return Failure(FailureKind.MISSING_TARGET, (pkg,), summary=line)
	return None


def _unsatisfied(lines: list[str]) -> Failure | None:
	for line in lines:
		match = _UNSATISFIED.search(line)
		if match and (pkg := _clean(match['pkg'])):
			return Failure(
				FailureKind.UNSATISFIED_DEPENDENCY, (pkg,), summary=line
			)
	return None


def _last_error(lines: list[str]) -> str:
	# the most recent 'error:' line is usually the one that matters
	for line in reversed(lines):
		if match := _ERROR_LINE.match(line):
			return match['message']
	return lines[-1] if lines else ''


def _clean(name: str) -> str:
	return name.strip(_TRAILING)
