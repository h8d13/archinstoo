import argparse
import difflib
import json
import sys
import urllib.error
import urllib.parse
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn, Self, override
from urllib.request import Request, urlopen

from pydantic.dataclasses import dataclass as p_dataclass

from archinstall.lib.models.application import ApplicationConfiguration, ZramConfiguration
from archinstall.lib.models.authentication import AuthenticationConfiguration
from archinstall.lib.models.bootloader import BootloaderConfiguration
from archinstall.lib.models.device import DiskLayoutConfiguration
from archinstall.lib.models.locale import LocaleConfiguration
from archinstall.lib.models.mirrors import MirrorConfiguration
from archinstall.lib.models.network import NetworkConfiguration
from archinstall.lib.models.profile import ProfileConfiguration
from archinstall.lib.output import error, warn
from archinstall.lib.translationhandler import Language, translation_handler


class SuggestArgumentParser(ArgumentParser):
	# use difflib to suggest on typos with args

	@override
	def error(self, message: str) -> NoReturn:
		if 'unrecognized arguments' in message:
			bad_arg = message.split(':')[-1].strip().split()[0]
			valid_options = [opt for a in self._actions for opt in a.option_strings]
			suggestions = difflib.get_close_matches(bad_arg, valid_options, n=1, cutoff=0.6)
			if suggestions:
				message += f'\n\nDid you mean: {suggestions[0]}'
		super().error(message)


@p_dataclass
class Arguments:
	config: Path | None = None
	config_url: str | None = None
	silent: bool = False
	dry_run: bool = False
	script: str | None = None
	mountpoint: Path = Path('/mnt')
	skip_ntp: bool = False
	skip_wkd: bool = False
	skip_boot: bool = False
	debug: bool = False
	offline: bool = False
	no_pkg_lookups: bool = False
	advanced: bool = False


@dataclass
class ArchConfig:
	script: str | None = None
	locale_config: LocaleConfiguration | None = None
	archinstall_language: Language = field(default_factory=lambda: translation_handler.get_language_by_abbr('en'))
	disk_config: DiskLayoutConfiguration | None = None
	profile_config: ProfileConfiguration | None = None
	mirror_config: MirrorConfiguration | None = None
	network_config: NetworkConfiguration | None = None
	bootloader_config: BootloaderConfiguration | None = None
	app_config: ApplicationConfiguration | None = None
	auth_config: AuthenticationConfiguration | None = None
	swap: ZramConfiguration | None = None
	hostname: str = 'archlinux'
	kernels: list[str] = field(default_factory=lambda: ['linux'])
	kernel_headers: bool = False
	ntp: bool = True
	packages: list[str] = field(default_factory=list)
	parallel_downloads: int = 0
	timezone: str | None = None
	services: list[str] = field(default_factory=list)
	custom_commands: list[str] = field(
		default_factory=lambda: [
			'#cd /home/user; git clone <url>',
			'#chown -R user:user /home/user/repo',
		]
	)
	bug_report_url: str = 'https://github.com/h8d13/archinstoo'

	def safe_json(self) -> dict[str, Any]:
		config: Any = {
			'script': self.script,
			'archinstall-language': self.archinstall_language.json(),
			'hostname': self.hostname,
			'kernels': self.kernels,
			'kernel_headers': self.kernel_headers,
			'ntp': self.ntp,
			'packages': self.packages,
			'parallel_downloads': self.parallel_downloads,
			'swap': self.swap,
			'timezone': self.timezone,
			'services': self.services,
			'custom_commands': self.custom_commands,
			'bug_report_url': self.bug_report_url,
			'bootloader_config': self.bootloader_config.json() if self.bootloader_config else None,
			'app_config': self.app_config.json() if self.app_config else None,
			'auth_config': self.auth_config.json() if self.auth_config else None,
		}

		if self.locale_config:
			config['locale_config'] = self.locale_config.json()

		if self.disk_config:
			config['disk_config'] = self.disk_config.json()

		if self.profile_config:
			config['profile_config'] = self.profile_config.json()

		if self.mirror_config:
			config['mirror_config'] = self.mirror_config.json()

		if self.network_config:
			config['network_config'] = self.network_config.json()

		return config

	@classmethod
	def from_config(cls, args_config: dict[str, Any], args: Arguments) -> Self:
		arch_config = cls()

		arch_config.locale_config = LocaleConfiguration.parse_arg(args_config)

		if script := args_config.get('script', None):
			arch_config.script = script

		if archinstall_lang := args_config.get('archinstall-language', None):
			arch_config.archinstall_language = translation_handler.get_language_by_name(archinstall_lang)

		if disk_config := args_config.get('disk_config', {}):
			arch_config.disk_config = DiskLayoutConfiguration.parse_arg(disk_config)

		if profile_config := args_config.get('profile_config', None):
			arch_config.profile_config = ProfileConfiguration.parse_arg(profile_config)

		if mirror_config := args_config.get('mirror_config', None):
			arch_config.mirror_config = MirrorConfiguration.parse_args(mirror_config)

		if net_config := args_config.get('network_config', None):
			arch_config.network_config = NetworkConfiguration.parse_arg(net_config)

		if bootloader_config_dict := args_config.get('bootloader_config', None):
			arch_config.bootloader_config = BootloaderConfiguration.parse_arg(bootloader_config_dict, args.skip_boot)

		if app_config_args := args_config.get('app_config', None):
			arch_config.app_config = ApplicationConfiguration.parse_arg(app_config_args)

		if auth_config_args := args_config.get('auth_config', None):
			arch_config.auth_config = AuthenticationConfiguration.parse_arg(auth_config_args)

		if hostname := args_config.get('hostname', ''):
			arch_config.hostname = hostname

		if kernels := args_config.get('kernels', []):
			arch_config.kernels = kernels

		arch_config.kernel_headers = args_config.get('kernel_headers', False)

		arch_config.ntp = args_config.get('ntp', True)

		if packages := args_config.get('packages', []):
			arch_config.packages = packages

		if parallel_downloads := args_config.get('parallel_downloads', 0):
			arch_config.parallel_downloads = parallel_downloads

		swap_arg = args_config.get('swap')
		if swap_arg is not None:
			arch_config.swap = ZramConfiguration.parse_arg(swap_arg)

		if timezone := args_config.get('timezone'):
			arch_config.timezone = timezone

		if services := args_config.get('services', []):
			arch_config.services = services

		if custom_commands := args_config.get('custom_commands', []):
			arch_config.custom_commands = custom_commands

		if bug_report_url := args_config.get('bug_report_url', None):
			arch_config.bug_report_url = bug_report_url

		return arch_config


class ArchConfigHandler:
	def __init__(self) -> None:
		self._parser: SuggestArgumentParser = self._define_arguments()
		args: Arguments = self._parse_args()
		self._args = args

		config = self._parse_config()

		try:
			self._config = ArchConfig.from_config(config, args)
		except ValueError as err:
			warn(str(err))
			sys.exit(1)

	@property
	def config(self) -> ArchConfig:
		return self._config

	@property
	def args(self) -> Arguments:
		return self._args

	def get_script(self) -> str:
		if script := self.args.script:
			return script

		if script := self.config.script:
			return script

		return 'guided'

	def print_help(self) -> None:
		self._parser.print_help()

	def _define_arguments(self) -> SuggestArgumentParser:
		parser = SuggestArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
		parser.add_argument(
			'--config',
			type=Path,
			nargs='?',
			default=None,
			help='JSON configuration file',
		)
		parser.add_argument(
			'--config-url',
			type=str,
			nargs='?',
			default=None,
			help='Url to a JSON configuration file',
		)
		parser.add_argument(
			'--silent',
			action='store_true',
			default=False,
			help='WARNING: Disables all prompts for input and confirmation. If no configuration is provided, this is ignored',
		)
		parser.add_argument(
			'--dry-run',
			action='store_true',
			default=False,
			help='Generates a configuration file and then exits instead of performing an installation',
		)
		parser.add_argument(
			'--script',
			nargs='?',
			help='Script to run for installation',
			type=str,
		)
		parser.add_argument(
			'--mountpoint',
			type=Path,
			nargs='?',
			default=Path('/mnt'),
			help='Define an alternate mount point for installation',
		)
		parser.add_argument(
			'--skip-ntp',
			action='store_true',
			help='Disables NTP checks during installation',
			default=False,
		)
		parser.add_argument(
			'--skip-wkd',
			action='store_true',
			help='Disables checking if archlinux keyring wkd sync is complete.',
			default=False,
		)
		parser.add_argument(
			'--skip-boot',
			action='store_true',
			help='Disables installation of a boot loader (note: only use this when problems arise with the boot loader step).',
			default=False,
		)
		parser.add_argument(
			'--debug',
			action='store_true',
			default=False,
			help='Adds debug info into the log',
		)
		parser.add_argument(
			'--offline',
			action='store_true',
			default=False,
			help='Disabled online upstream services such as package search and key-ring auto update.',
		)
		parser.add_argument(
			'--no-pkg-lookups',
			action='store_true',
			default=False,
			help='Disabled package validation specifically prior to starting installation.',
		)
		parser.add_argument(
			'--advanced',
			action='store_true',
			default=False,
			help='Enabled advanced options',
		)

		return parser

	def _parse_args(self) -> Arguments:
		argparse_args = vars(self._parser.parse_args())
		args: Arguments = Arguments(**argparse_args)

		# amend the parameters (check internal consistency)
		# Installation can't be silent if config is not passed
		if args.config is None and args.config_url is None:
			args.silent = False

		return args

	def _parse_config(self) -> dict[str, Any]:
		config: dict[str, Any] = {}
		config_data: str | None = None

		if self._args.config is not None:
			config_data = self._read_file(self._args.config)
		elif self._args.config_url is not None:
			config_data = self._fetch_from_url(self._args.config_url)

		if config_data is not None:
			config.update(json.loads(config_data))

		config = self._cleanup_config(config)

		return config

	def _fetch_from_url(self, url: str) -> str:
		if urllib.parse.urlparse(url).scheme:
			try:
				req = Request(url, headers={'User-Agent': 'ArchInstall'})
				with urlopen(req) as resp:
					return resp.read().decode('utf-8')
			except urllib.error.HTTPError as err:
				error(f'Could not fetch JSON from {url}: {err}')
		else:
			error('Not a valid url')

		sys.exit(1)

	def _read_file(self, path: Path) -> str:
		if not path.exists():
			error(f'Could not find file {path}')
			sys.exit(1)

		return path.read_text()

	def _cleanup_config(self, config: Namespace | dict[str, Any]) -> dict[str, Any]:
		clean_args = {}
		for key, val in config.items():
			if isinstance(val, dict):
				val = self._cleanup_config(val)

			if val is not None:
				clean_args[key] = val

		return clean_args


arch_config_handler: ArchConfigHandler = ArchConfigHandler()
