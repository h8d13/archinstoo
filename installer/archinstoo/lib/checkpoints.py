import importlib
import textwrap
from pathlib import Path
from shutil import rmtree

from archinstoo.lib.output import TARGET_STATE_DIR, error, info, log, logger, warn


def clean_logs() -> None:
	# --clean: wipe the log directory, sibling of clean_cache below
	for item in logger.directory.iterdir():
		# .info reuses the file type gleaned from iterdir()'s scandir, no extra stat
		if item.info.is_dir():
			rmtree(item)
		else:
			item.unlink()


def _script_not_found(script: str) -> SystemExit:
	error(f'Script: {script} does not exist. Try `--script list` to see your options.')
	return SystemExit(1)


def _script_parts(script: str) -> list[str]:
	# subfolders are namespaces: dev.vm loads scripts/dev/vm.py
	parts = script.split('.')
	# '', '..', 'dev/vm' or '-x' would reach import_module as a relative or bogus name
	if not all(part.isidentifier() for part in parts):
		raise _script_not_found(script)
	return parts


def _run_script(script: str) -> None:
	parts = _script_parts(script)
	module = '.'.join(('archinstoo.scripts', *parts))
	try:
		# by importing we automatically run it
		importlib.import_module(module)
	except ModuleNotFoundError as e:
		# only the script or one of its namespaces missing is a usage error; a
		# bad import inside the script (`e.name` is the module it asked for)
		# must surface as the crash it is, or `--script` exits 0 having done nothing
		namespaces = {'.'.join(('archinstoo.scripts', *parts[:i])) for i in range(1, len(parts) + 1)}
		if e.name not in namespaces:
			raise
		raise _script_not_found(script) from e


def clean_cache(root: Path) -> None:
	# only clean a source checkout: an installed copy has no pyproject.toml
	# beside it, and its caches belong to the package manager
	if not (root / 'pyproject.toml').is_file():
		return

	deleted = []

	info('Cleaning up...')
	try:
		for dirpath, dirnames, _ in root.walk():
			for dirname in dirnames:
				if dirname.lower() == '__pycache__':
					full_path = dirpath / dirname
					try:
						rmtree(full_path)
						deleted.append(full_path)
					except Exception as e:
						info(f'Failed to delete {full_path}: {e}')
	except KeyboardInterrupt, PermissionError:
		pass

	if deleted:
		info(f'Done. {len(deleted)} cache folder(s) deleted.')


def report_outcome(target: Path, steps: dict[str, bool]) -> None:
	# the steps a script left unreached. A crash never gets here: the top
	# level prints the traceback, bug report url and log path for those
	missing = [step for step, done in steps.items() if not done]
	if missing:
		warn('Some required steps were not reached before leaving the installer:')
		for step in missing:
			warn(f' - {step}')
		warn(f'Detailed error logs can be found at: {logger.directory}')
		return

	closing = 'Changes are live on the running system.' if target == Path('/') else 'You may reboot when ready.'
	log(
		textwrap.dedent(f"""\
			Installation completed without any errors.
			Log files available at {logger.directory} and in target {TARGET_STATE_DIR}.
			{closing}
		"""),
		fg='green',
	)
