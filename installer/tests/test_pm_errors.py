# classify() turns recorded pacman output into the failure it describes, and
# _recovery_options() only offers ways out that can actually change the
# outcome: dropping a package pulled in as a dependency would be a no-op.

from archinstoo.lib.pm.errors import FailureKind, classify, strip_version
from archinstoo.lib.pm.pacman import _recovery_options

CONFLICT = """\
:: Synchronizing package databases...
resolving dependencies...
looking for conflicting packages...
:: pipewire-jack and jack2 are in conflict. Remove jack2? [y/N]
error: unresolvable package conflicts detected
error: failed to prepare transaction (conflicting dependencies)
"""

# recorded on an archinstoo ISO: current pacman names both sides with their
# full version, epoch included
CONFLICT_VERSIONED = """\
warning: pipewire-jack-1:1.6.10-1 is up to date -- skipping
resolving dependencies...
looking for conflicting packages...
:: jack2-1.9.22-2 and pipewire-jack-1:1.6.10-1 are in conflict (jack). \
Remove pipewire-jack? [y/N]
error: unresolvable package conflicts detected
error: failed to prepare transaction (conflicting dependencies)
:: jack2-1.9.22-2 and pipewire-jack-1:1.6.10-1 are in conflict
==> ERROR: Failed to install packages to new root
"""

CONFLICT_WITH_PROVIDER = """\
:: iptables-nft and iptables are in conflict (iptables)
error: unresolvable package conflicts detected
"""

MISSING_TARGET = """\
:: Synchronizing package databases...
error: target not found: linux-zen-headerz
"""

FILE_EXISTS = """\
checking for file conflicts...
error: failed to commit transaction (conflicting files)
filesystem: /usr/lib/os-release exists in filesystem
glibc: /usr/lib/locale/locale-archive exists in filesystem (owned by glibc)
Errors occurred, no packages were upgraded.
"""

UNSATISFIED = """\
resolving dependencies...
:: unable to satisfy dependency 'libfoo=2.0' required by bar
error: failed to prepare transaction (could not satisfy dependencies)
"""

DOWNLOAD_FAILURE = """\
error: failed retrieving file 'core.db' from mirror.example.org : timed out
error: failed to synchronize all databases (unexpected error)
"""


def _keys(failure_text: str, droppable: list[str], repeated: bool) -> list[str]:
	options = _recovery_options(classify(failure_text), droppable, repeated)
	return [option.key for option in options]


def test_classify_conflict() -> None:
	failure = classify(CONFLICT)

	assert failure.kind == FailureKind.CONFLICT
	# 'are in conflict. Remove jack2?': the '.' is not part of the name
	assert failure.candidates == ('pipewire-jack', 'jack2')


def test_classify_conflict_drops_pacman_versions() -> None:
	# with the versions left on, neither name matched the request list and
	# a conflict between two requested packages read as one between deps
	failure = classify(CONFLICT_VERSIONED)

	assert failure.kind == FailureKind.CONFLICT
	assert failure.candidates == ('jack2', 'pipewire-jack')
	assert _keys(
		CONFLICT_VERSIONED, ['jack2', 'pipewire-jack'], repeated=False
	) == ['keep_first', 'keep_second', 'drop']


def test_classify_conflict_keeps_names_that_end_in_a_number() -> None:
	failure = classify(':: dotnet-runtime-8.0 and dotnet-host are in conflict')

	assert failure.candidates == ('dotnet-runtime-8.0', 'dotnet-host')


def test_classify_conflict_with_provider_suffix() -> None:
	failure = classify(CONFLICT_WITH_PROVIDER)

	assert failure.kind == FailureKind.CONFLICT
	assert failure.candidates == ('iptables-nft', 'iptables')


def test_classify_missing_target() -> None:
	failure = classify(MISSING_TARGET)

	assert failure.kind == FailureKind.MISSING_TARGET
	assert failure.candidates == ('linux-zen-headerz',)


def test_classify_file_conflict_collects_every_path() -> None:
	failure = classify(FILE_EXISTS)

	assert failure.kind == FailureKind.FILE_EXISTS
	assert failure.candidates == ('filesystem', 'glibc')
	assert failure.paths == (
		'/usr/lib/os-release',
		'/usr/lib/locale/locale-archive',
	)


def test_classify_unsatisfied_dependency() -> None:
	failure = classify(UNSATISFIED)

	assert failure.kind == FailureKind.UNSATISFIED_DEPENDENCY
	assert failure.candidates == ('bar',)


def test_classify_unknown_keeps_the_last_error_line() -> None:
	failure = classify(DOWNLOAD_FAILURE)

	assert failure.kind == FailureKind.UNKNOWN
	assert failure.candidates == ()
	assert failure.summary == (
		'failed to synchronize all databases (unexpected error)'
	)


def test_a_conflict_wins_over_the_trailing_error_line() -> None:
	assert classify(CONFLICT + DOWNLOAD_FAILURE).kind == FailureKind.CONFLICT


def test_classify_empty_output() -> None:
	failure = classify('')

	assert failure.kind == FailureKind.UNKNOWN
	assert not failure.summary


def test_strip_version() -> None:
	assert strip_version('foo>=1.2') == 'foo'
	assert strip_version('foo=1.2') == 'foo'
	assert strip_version('foo>2:1.2-3') == 'foo'
	# names that end in a version are names, not versioned specs
	assert strip_version('dotnet-runtime-8.0') == 'dotnet-runtime-8.0'
	assert strip_version('sdl2-compat') == 'sdl2-compat'


def test_conflict_between_two_requested_packages() -> None:
	assert _keys(CONFLICT, ['pipewire-jack', 'jack2'], repeated=False) == [
		'keep_first',
		'keep_second',
		'drop',
	]


def test_conflict_between_dependencies_offers_nothing_to_drop() -> None:
	assert _keys(CONFLICT, [], repeated=False) == []


def test_conflict_with_one_requested_package_drops_only_that_one() -> None:
	assert _keys(CONFLICT, ['jack2'], repeated=False) == ['drop']


def test_missing_target_can_be_renamed_or_dropped() -> None:
	assert _keys(MISSING_TARGET, ['linux-zen-headerz'], repeated=False) == [
		'rename',
		'drop',
	]


def test_file_conflict_can_overwrite() -> None:
	assert _keys(FILE_EXISTS, [], repeated=False) == ['overwrite']


def test_unknown_failure_can_retry_or_skip() -> None:
	assert _keys(DOWNLOAD_FAILURE, [], repeated=False) == ['retry', 'abandon']


def test_a_repeated_failure_stops_offering_the_same_way_out() -> None:
	repeated = _keys(CONFLICT, ['pipewire-jack', 'jack2'], repeated=True)

	assert repeated == ['abandon']
