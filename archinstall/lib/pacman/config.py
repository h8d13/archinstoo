import re
from pathlib import Path
from shutil import copy2
from typing import TYPE_CHECKING

from ..models.packages import Repository
from ..output import debug

if TYPE_CHECKING:
	from ..models.mirrors import CustomRepository


class PacmanConfig:
	def __init__(self, target: Path | None):
		self._config_path = Path('/etc') / 'pacman.conf'
		self._config_remote_path: Path | None = None

		if target:
			self._config_remote_path = target / 'etc' / 'pacman.conf'

		self._repositories: list[Repository] = []
		self._custom_repositories: list['CustomRepository'] = []

	def enable(self, repo: Repository | list[Repository]) -> None:
		if not isinstance(repo, list):
			repo = [repo]

		self._repositories += repo

	def add_custom_repo(self, repo: 'CustomRepository | list[CustomRepository]') -> None:
		if not isinstance(repo, list):
			repo = [repo]

		self._custom_repositories += repo

	def apply(self) -> None:
		if self._repositories:
			self._apply_optional_repos()

		if self._custom_repositories:
			self._apply_custom_repos()

	def _apply_optional_repos(self) -> None:
		repos_to_enable = []
		for repo in self._repositories:
			if repo == Repository.Testing:
				repos_to_enable.extend(['core-testing', 'extra-testing', 'multilib-testing'])
			else:
				repos_to_enable.append(repo.value)

		content = self._config_path.read_text().splitlines(keepends=True)

		for row, line in enumerate(content):
			# Check if this is a commented repository section that needs to be enabled
			match = re.match(r'^#\s*\[(.*)\]', line)

			if match and match.group(1) in repos_to_enable:
				# uncomment the repository section line, properly removing # and any spaces
				content[row] = re.sub(r'^#\s*', '', line)

				# also uncomment the next line (Include statement) if it exists and is commented
				if row + 1 < len(content) and content[row + 1].lstrip().startswith('#'):
					content[row + 1] = re.sub(r'^#\s*', '', content[row + 1])

		# Write the modified content back to the file
		with open(self._config_path, 'w') as f:
			f.writelines(content)

	def _apply_custom_repos(self) -> None:
		content = self._config_path.read_text()

		# Separate priority and normal repos
		priority_repos = [r for r in self._custom_repositories if r.priority]
		normal_repos = [r for r in self._custom_repositories if not r.priority]

		# Insert priority repos before first default repository
		if priority_repos:
			priority_config = self._format_repos(priority_repos)
			debug(f'Adding priority repositories: {[r.name for r in priority_repos]}')

			# Find the [core] repository (always first in default pacman.conf)
			match = re.search(r'\n(\[core\])', content)

			if match:
				# Insert before the first default repository
				insert_pos = match.start()
				content = content[:insert_pos] + priority_config + content[insert_pos:]
			else:
				# Fallback: append to end if no default repos found
				debug('No default repositories found, appending priority repos to end')
				content += priority_config

		# Append normal repos to the end
		if normal_repos:
			normal_config = self._format_repos(normal_repos)
			debug(f'Adding custom repositories: {[r.name for r in normal_repos]}')
			content += normal_config

		# Write back to file
		self._config_path.write_text(content)

	def _format_repos(self, repos: 'list[CustomRepository]') -> str:
		config = ''
		for repo in repos:
			config += f'\n[{repo.name}]\n'
			config += f'SigLevel = {repo.sign_check.value} {repo.sign_option.value}\n'
			config += f'Server = {repo.url}\n'
		return config

	def persist(self) -> None:
		if (self._repositories or self._custom_repositories) and self._config_remote_path:
			copy2(self._config_path, self._config_remote_path)
