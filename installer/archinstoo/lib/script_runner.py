import importlib
import importlib.util

from archinstoo.lib.output import error

# resolving and running `--script <name>`: a script is a module under
# archinstoo.scripts whose main() is the entry. One without a main() still
# runs as it always did, on import, at module level


def _script_not_found(script: str) -> SystemExit:
	error(f'No such script: {script}. Try `--script list` to see your options.')
	return SystemExit(1)


def _script_parts(script: str) -> list[str]:
	# subfolders are namespaces: dev.vm loads scripts/dev/vm.py
	parts = script.split('.')
	# '', '..', 'dev/vm' or '-x' would reach import_module as a
	# relative or bogus name
	if not all(part.isidentifier() for part in parts):
		raise _script_not_found(script)
	return parts


def _check_script(script: str) -> None:
	# find it without importing it (its imports need what bootstrap has yet
	# to install, and a script without main() runs on import), so a missing
	# name or a bare namespace (dev) fails before root checks and bootstrap
	module = '.'.join(('archinstoo.scripts', *_script_parts(script)))
	try:
		spec = importlib.util.find_spec(module)
	except ModuleNotFoundError:
		spec = None
	if spec is None or spec.submodule_search_locations is not None:
		raise _script_not_found(script)


def _run_script(script: str) -> None:
	parts = _script_parts(script)
	module = '.'.join(('archinstoo.scripts', *parts))
	try:
		loaded = importlib.import_module(module)
	except ModuleNotFoundError as e:
		# only the script or one of its namespaces missing is a usage error; a
		# bad import inside the script (`e.name` is the module it asked for)
		# must surface as the crash it is, or `--script` exits
		# 0 having done nothing
		namespaces = {
			'.'.join(('archinstoo.scripts', *parts[:i]))
			for i in range(1, len(parts) + 1)
		}
		if e.name not in namespaces:
			raise
		raise _script_not_found(script) from e

	entry = getattr(loaded, 'main', None)
	if not callable(entry):
		return

	# an int is an exit status, as from a console entry point
	rc = entry()
	if isinstance(rc, int) and rc:
		raise SystemExit(rc)
