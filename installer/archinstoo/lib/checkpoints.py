import importlib
import os
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


def _run_script(script: str) -> None:
	try:
		# by importing we automatically run it
		importlib.import_module(f'archinstoo.scripts.{script}')
	except ModuleNotFoundError as e:
		# only the script itself missing is a usage error; a bad import inside
		# the script (`e.name` is the module it asked for) must surface as the
		# crash it is, or `--script` exits 0 having done nothing
		if e.name != f'archinstoo.scripts.{script}':
			raise
		error(f'Script: {script} does not exist. Try `--script list` to see your options.')
		raise SystemExit(1) from e


def clean_cache(root_dir: str) -> None:
	# only clean if running from source (archinstoo dir exists in cwd)
	if not (Path(root_dir) / 'archinstoo').is_dir():
		return

	deleted = []

	info('Cleaning up...')
	try:
		for dirpath, dirnames, _ in os.walk(root_dir):
			for dirname in dirnames:
				if dirname.lower() == '__pycache__':
					full_path = Path(dirpath) / dirname
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

	# live/packages install onto the running system: the changes are
	# already in effect, there is nothing to reboot into
	closing = 'Changes are live on the running system.' if target == Path('/') else 'You may reboot when ready.'
	log(
		f'Installation completed without any errors.\nLog files available at {logger.directory} and in target {TARGET_STATE_DIR}.\n{closing}\n',
		fg='green',
	)
