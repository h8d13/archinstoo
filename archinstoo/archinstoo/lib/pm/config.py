import atexit
import re
from pathlib import Path
from typing import TYPE_CHECKING, assert_never

from archinstoo.lib.models.mirrors import CustomRepository, SignCheck, SignOption
from archinstoo.lib.models.packages import Repository
from archinstoo.lib.pathnames import PACMAN_CONF
from archinstoo.lib.translationhandler import tr
from archinstoo.lib.tui.curses_menu import EditMenu
from archinstoo.lib.tui.result import ResultType
from archinstoo.lib.utils.env import Os


def set_parallel_downloads(preset: int | None = None) -> int | None:
	max_recommended = 5

	header = tr('This option enables the number of parallel downloads that can occur during package downloads') + '\n'
	header += tr('Enter the number of parallel downloads to be enabled.\n\nNote:\n')
	header += tr(' - Maximum recommended value : {} ( Allows {} parallel downloads at a time )').format(max_recommended, max_recommended) + '\n'
	header += tr(' - Disable/Default : 0 ( Disables parallel downloading, allows only 1 download at a time )\n')

	def validator(s: str | None) -> str | None:
		if s is not None:
			try:
				value = int(s)
				if value >= 0:
					return None
			except Exception:
				pass

		return tr('Invalid download number')

	result = EditMenu(
		tr('Number downloads'),
		header=header,
		allow_skip=True,
		allow_reset=True,
		validator=validator,
		default_text=str(preset) if preset is not None else None,
	).input()

	match result.type_:
		case ResultType.Skip:
			return preset
		case ResultType.Reset:
			return 0
		case ResultType.Selection:
			downloads: int = int(result.text())
		case _:
			assert_never(result.type_)

	with PACMAN_CONF.open() as f:
		pacman_conf = f.read().split('\n')

	with PACMAN_CONF.open('w') as fwrite:
		for line in pacman_conf:
			if 'ParallelDownloads' in line:
				fwrite.write(f'ParallelDownloads = {downloads}\n')
			else:
				fwrite.write(f'{line}\n')

	return downloads


# Standard Arch repos to ignore when detecting custom repos
_STANDARD_REPOS = {
	'options',
	'core',
	'extra',
	'multilib',
	'testing',
	'core-testing',
	'extra-testing',
	'multilib-testing',
	'community',
	'community-testing',
}

if TYPE_CHECKING:
	from archinstoo.lib.models.mirrors import PacmanConfiguration


class PacmanConfig:
	def __init__(self, target: Path | None):
		self._config_remote_path: Path | None = None

		if target:
			self._config_remote_path = target / PACMAN_CONF.relative_to_root()

		self._repositories: list[Repository] = []
		self._custom_repositories: list[CustomRepository] = []
		self._misc_options: list[str] = []

	def enable(self, repo: Repository | list[Repository]) -> None:
		if not isinstance(repo, list):
			repo = [repo]

		self._repositories += repo

	def enable_custom(self, repos: list[CustomRepository]) -> None:
		self._custom_repositories = repos

	def enable_options(self, options: list[str]) -> None:
		"""Enable misc options like Color, ILoveCandy, VerbosePkgLists"""
		self._misc_options = options

	def apply(self) -> None:
		if not self._repositories and not self._custom_repositories and not self._misc_options:
			return

		repos_to_enable = []
		for repo in self._repositories:
			if repo == Repository.Testing:
				repos_to_enable.extend(['core-testing', 'extra-testing', 'multilib-testing'])
			else:
				repos_to_enable.append(repo.value)

		content = PACMAN_CONF.read_text().splitlines(keepends=True)
		options_found: set[str] = set()
		last_opt_row = 0

		for row, line in enumerate(content):
			# Uncomment misc options (Color, ILoveCandy, etc.)
			for opt in self._misc_options:
				if re.match(rf'^#?\s*{opt}\b', line):
					options_found.add(opt)
					last_opt_row = row
					if line.lstrip().startswith('#'):
						content[row] = re.sub(r'^#\s*', '', line)
					break

			# Check if this is a commented repository section that needs to be enabled
			match = re.match(r'^#\s*\[(.*)\]', line)

			if match and match.group(1) in repos_to_enable:
				# uncomment the repository section line, properly removing # and any spaces
				content[row] = re.sub(r'^#\s*', '', line)

				# also uncomment the next line (Include statement) if it exists and is commented
				if row + 1 < len(content) and content[row + 1].lstrip().startswith('#'):
					content[row + 1] = re.sub(r'^#\s*', '', content[row + 1])

		for opt in set(self._misc_options) - options_found:
			content.insert(last_opt_row + 1, f'{opt}\n')

		# Append custom repositories (skip if already exists)
		content_str = ''.join(content)
		core_idx = next((i for i, line in enumerate(content) if re.match(r'^\[core\]', line)), None)

		for custom in self._custom_repositories:
			if f'[{custom.name}]' in content_str:
				continue
			if custom.url.startswith('file://'):
				# Insert before [core] to give priority (mirrors ISOMOD_CACHE behaviour)
				insert_at = core_idx if core_idx is not None else len(content)
				content[insert_at:insert_at] = [
					f'[{custom.name}]\n',
					f'SigLevel = {custom.sign_check.value} {custom.sign_option.value}\n',
					f'Server = {custom.url}\n',
					'\n',
				]
			else:
				content.append(f'\n[{custom.name}]\n')
				content.append(f'SigLevel = {custom.sign_check.value} {custom.sign_option.value}\n')
				content.append(f'Server = {custom.url}\n')

		# Apply temp using backup then revert on exit handler
		if Os.running_from_host():
			temp_copy = PACMAN_CONF.with_suffix('.bak')
			PACMAN_CONF.copy(temp_copy, preserve_metadata=True)
			atexit.register(lambda: temp_copy.copy(PACMAN_CONF, preserve_metadata=True))

		with PACMAN_CONF.open('w') as f:
			f.writelines(content)

	def persist(self) -> None:
		has_changes = self._repositories or self._custom_repositories or self._misc_options
		if has_changes and self._config_remote_path and not PACMAN_CONF.samefile(self._config_remote_path):
			content = PACMAN_CONF.read_text()
			content = re.sub(r'\n\[[^\]]+\]\nSigLevel = [^\n]+\nServer = file://[^\n]+\n', '', content)
			self._config_remote_path.write_text(content)

	@classmethod
	def apply_config(cls, config: PacmanConfiguration) -> None:
		"""Apply a PacmanConfiguration to the live system."""
		if not config.optional_repositories and not config.custom_repositories and not config.pacman_options:
			return
		pacman = cls(None)
		if config.optional_repositories:
			pacman.enable(config.optional_repositories)
		if config.custom_repositories:
			pacman.enable_custom(config.custom_repositories)
		if config.pacman_options:
			pacman.enable_options(config.pacman_options)
		pacman.apply()

	@classmethod
	def get_existing_custom_repos(cls) -> list[CustomRepository]:
		"""Parse pacman.conf for existing custom repositories."""
		content = PACMAN_CONF.read_text()
		repos: list[CustomRepository] = []

		for match in re.finditer(r'\[([^\]]+)\]\s*\n([^[]*)', content):
			name = match.group(1)
			if name.lower() in _STANDARD_REPOS:
				continue

			block = match.group(2)
			server = re.search(r'^Server\s*=\s*(.+)$', block, re.MULTILINE)
			if not server:
				continue

			sig = re.search(r'^SigLevel\s*=\s*(.+)$', block, re.MULTILINE)
			sign_check, sign_option = SignCheck.Never, SignOption.TrustAll

			if sig:
				for part in sig.group(1).split():
					if part in [e.value for e in SignCheck]:
						sign_check = SignCheck(part)
					elif part in [e.value for e in SignOption]:
						sign_option = SignOption(part)

			repos.append(CustomRepository(name, server.group(1).strip(), sign_check, sign_option))

		return repos
