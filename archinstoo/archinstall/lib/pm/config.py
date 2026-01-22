import atexit
import re
from pathlib import Path
from shutil import copy2
from typing import TYPE_CHECKING

from ..models.mirrors import CustomRepository
from ..models.packages import Repository
from ..utils.env import running_from_host

if TYPE_CHECKING:
	from ..models.mirrors import PacmanConfiguration


class PacmanConfig:
	def __init__(self, target: Path | None):
		self._config_path = Path('/etc') / 'pacman.conf'
		self._config_remote_path: Path | None = None

		if target:
			self._config_remote_path = target / 'etc' / 'pacman.conf'

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

		content = self._config_path.read_text().splitlines(keepends=True)

		for row, line in enumerate(content):
			# Uncomment misc options (Color, ILoveCandy, etc.)
			for opt in self._misc_options:
				if re.match(rf'^#\s*{opt}\b', line):
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

		# Append custom repositories (skip if already exists)
		content_str = ''.join(content)
		for custom in self._custom_repositories:
			if f'[{custom.name}]' not in content_str:
				content.append(f'\n[{custom.name}]\n')
				content.append(f'SigLevel = {custom.sign_check.value} {custom.sign_option.value}\n')
				content.append(f'Server = {custom.url}\n')

		# Apply temp using backup then revert on exit handler
		if running_from_host():
			temp_copy = self._config_path.with_suffix('.bak')
			copy2(self._config_path, temp_copy)
			atexit.register(lambda: copy2(temp_copy, self._config_path))

		with open(self._config_path, 'w') as f:
			f.writelines(content)

	def persist(self) -> None:
		has_changes = self._repositories or self._custom_repositories or self._misc_options
		if has_changes and self._config_remote_path:
			copy2(self._config_path, self._config_remote_path)

	@classmethod
	def apply_config(cls, config: 'PacmanConfiguration') -> None:
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
