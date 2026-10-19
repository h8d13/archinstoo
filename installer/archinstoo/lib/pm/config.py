import contextlib
import re
from typing import TYPE_CHECKING, assert_never

from archinstoo.lib.models.mirrors import (
	RESERVED_REPO_NAMES,
	CustomRepository,
	SignCheck,
	SignOption,
)
from archinstoo.lib.models.packages import Repository
from archinstoo.lib.output import debug, info
from archinstoo.lib.pm.pacman import PACMAN_CONF, live
from archinstoo.lib.tui.curses_menu import EditMenu
from archinstoo.lib.tui.result import ResultType


def set_parallel_downloads(preset: int | None = None) -> int | None:
	max_recommended = 10

	header = f'Enter the number of parallel downloads (1-{max_recommended})'

	def validator(s: str | None) -> str | None:
		if s is not None:
			with contextlib.suppress(Exception):
				value = int(s)
				if 1 <= value <= max_recommended:
					return None

		return f'Value must be between 1 and {max_recommended}'

	result = EditMenu(
		'Number downloads',
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
			return 5
		case ResultType.Selection:
			downloads: int = int(result.text())
		case _:
			assert_never(result.type_)

	debug(f'Setting ParallelDownloads = {downloads}')
	conf = live(PACMAN_CONF)
	pacman_conf = [
		f'ParallelDownloads = {downloads}'
		if 'ParallelDownloads' in line
		else line
		for line in conf.read_text().splitlines()
	]
	conf.write_text('\n'.join(pacman_conf) + '\n')

	return downloads


if TYPE_CHECKING:
	from pathlib import Path

	from archinstoo.lib.models.mirrors import PacmanConfiguration


class PacmanConfig:
	def __init__(self, target: Path | None) -> None:
		# reads and writes go to the conf this instance was built for: the
		# live one, or the stock conf pacstrap installed in the target. The
		# two are never copied over each other, so the installed system
		# reflects the configuration and not the ISO that ran the installer
		self._target = target
		self._conf_path = (
			target / PACMAN_CONF.relative_to_root()
			if target
			else live(PACMAN_CONF)
		)

		self._repositories: list[Repository] = []
		self._custom_repositories: list[CustomRepository] = []
		self._misc_options: list[str] = []
		self._parallel_downloads: int | None = None

	def enable(self, repo: Repository | list[Repository]) -> None:
		if not isinstance(repo, list):
			repo = [repo]

		self._repositories += repo

	def enable_custom(self, repos: list[CustomRepository]) -> None:
		self._custom_repositories = repos

	def enable_options(self, options: list[str]) -> None:
		# Enable misc options like Color, ILoveCandy, VerbosePkgLists
		self._misc_options = options

	def set_downloads(self, downloads: int | None) -> None:
		self._parallel_downloads = downloads

	def apply(self) -> None:
		if (
			not self._repositories
			and not self._custom_repositories
			and not self._misc_options
			and not self._parallel_downloads
		):
			return

		repos_to_enable = []
		for repo in self._repositories:
			if repo == Repository.Testing:
				repos_to_enable.extend(
					[
						'core-testing',
						'extra-testing',
						'multilib-testing',
					]
				)
			else:
				repos_to_enable.append(repo.value)

		content = self._conf_path.read_text().splitlines(keepends=True)
		options_found: set[str] = set()
		last_opt_row = 0

		for row, line in enumerate(content):
			# Uncomment misc options (Color, ILoveCandy, etc.)
			for opt in self._misc_options:
				if re.match(rf'^#?\s*{opt}\b', line):
					options_found.add(opt)
					last_opt_row = row
					if line.lstrip().startswith('#'):
						content[row] = re.sub(
							r'^#\s*', '', line
						)
					break

			if self._parallel_downloads and re.match(
				r'^#?\s*ParallelDownloads\b', line
			):
				content[row] = (
					'ParallelDownloads = '
					f'{self._parallel_downloads}\n'
				)

			# Check if this is a commented repository section
			# that needs to be enabled
			match = re.match(r'^#\s*\[(.*)\]', line)

			if match and match.group(1) in repos_to_enable:
				# uncomment the repository section line, properly
				# removing # and any spaces
				content[row] = re.sub(r'^#\s*', '', line)

				# also uncomment the next line (Include statement) if it
				# exists and is commented
				if row + 1 < len(content) and content[
					row + 1
				].lstrip().startswith('#'):
					# item assignment only, the list is never
					# resized inside the loop
					content[row + 1] = re.sub(  # noqa: B909
						r'^#\s*', '', content[row + 1]
					)

		for opt in set(self._misc_options) - options_found:
			content.insert(last_opt_row + 1, f'{opt}\n')

		# Append custom repositories (skip if already exists)
		content_str = ''.join(content)
		core_idx = next(
			(
				i
				for i, line in enumerate(content)
				if re.match(r'^\[core\]', line)
			),
			None,
		)
		# advances past each block so priority repos keep their list order,
		# which is their priority order to pacman
		priority_at = core_idx if core_idx is not None else len(content)

		for custom in self._custom_repositories:
			if f'[{custom.name}]' in content_str:
				continue
			if custom.url.startswith('file://') and self._target:
				# an ISO-local cache is gone after reboot, it only ever
				# belonged to the conf doing the installing
				debug(
					'Skipping file:// repository '
					f'[{custom.name}] for the target'
				)
				continue

			block = [
				f'[{custom.name}]\n',
				(
					f'SigLevel = {custom.sign_check.value} '
					f'{custom.sign_option.value}\n'
				),
				f'Server = {custom.url}\n',
			]
			if custom.priority:
				content[priority_at:priority_at] = [*block, '\n']
				priority_at += len(block) + 1
			else:
				content += ['\n', *block]

		if repos_to_enable:
			info(
				f'Enabling repositories {", ".join(repos_to_enable)} '
				f'in {self._conf_path}'
			)
		for custom in self._custom_repositories:
			place = (
				'priority, above [core]'
				if custom.priority
				else 'appended'
			)
			debug(
				f'Custom repository [{custom.name}] -> '
				f'{custom.url} ({place})'
			)

		with self._conf_path.open('w') as f:
			f.writelines(content)

	@classmethod
	def apply_config(
		cls, config: PacmanConfiguration, target: Path | None = None
	) -> None:
		# Render a PacmanConfiguration into a conf: the live one before
		# pacstrap so it resolves from the chosen repos, the target's own
		# once pacstrap has installed one there.
		pacman = cls(target)
		if config.optional_repositories:
			pacman.enable(config.optional_repositories)
		if config.custom_repositories:
			pacman.enable_custom(config.custom_repositories)
		if config.pacman_options:
			pacman.enable_options(config.pacman_options)
		pacman.set_downloads(config.parallel_downloads)
		pacman.apply()

	@classmethod
	def get_existing_custom_repos(cls) -> list[CustomRepository]:
		# Parse pacman.conf for existing custom repositories.
		content = live(PACMAN_CONF).read_text()
		repos: list[CustomRepository] = []
		core = re.search(r'^\[core\]', content, re.MULTILINE)
		core_pos = core.start() if core else 0

		for match in re.finditer(r'\[([^\]]+)\]\s*\n([^[]*)', content):
			name = match.group(1)
			if name.lower() in RESERVED_REPO_NAMES:
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

			priority = match.start() < core_pos
			repos.append(
				CustomRepository(
					name,
					server.group(1).strip(),
					sign_check,
					sign_option,
					priority,
				)
			)

		return repos
