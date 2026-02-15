import argparse
import json
import shutil
import sys
import urllib.error
import urllib.parse
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Self, cast
from urllib.request import Request, urlopen

from archinstoo.lib.models.application import ApplicationConfiguration, ZramConfiguration
from archinstoo.lib.models.authentication import AuthenticationConfiguration
from archinstoo.lib.models.bootloader import BootloaderConfiguration
from archinstoo.lib.models.device import DiskLayoutConfiguration
from archinstoo.lib.models.init import InitHooks
from archinstoo.lib.models.locale import LocaleConfiguration
from archinstoo.lib.models.mirrors import PacmanConfiguration
from archinstoo.lib.models.network import NetworkConfiguration
from archinstoo.lib.models.profile import ProfileConfiguration
from archinstoo.lib.models.service import UserService
from archinstoo.lib.output import error, logger, warn
from archinstoo.lib.translationhandler import Language, translation_handler


def _set_direct(obj: Any, config: dict[str, Any], mapping: dict[str, str]) -> None:
	for key, attr in mapping.items():
		if value := config.get(key):
			setattr(obj, attr, value)


def _set_parsed(obj: Any, config: dict[str, Any], mapping: dict[str, tuple[type, str]]) -> None:
	for key, (klass, method) in mapping.items():
		if value := config.get(key):
			setattr(obj, key, getattr(klass, method)(value))


@dataclass
class Arguments:
	config: Path | None = None
	config_url: str | None = None
	dry_run: bool = False
	script: str | None = None
	mountpoint: Path = Path('/mnt')
	skip_ntp: bool = False
	skip_wkd: bool = False
	skip_boot: bool = False
	debug: bool = False
	offline: bool = False
	advanced: bool = False
	clean: bool = False


@dataclass
class ArchConfig:
	# Meta
	bug_report_url: str = 'https://github.com/h8d13/archinstoo'
	script: str = 'guided'
	# Menu order
	archinstoo_language: Language = field(default_factory=lambda: translation_handler.get_language_by_abbr('en'))
	bootloader_config: BootloaderConfiguration | None = None
	kernels: list[str] = field(default_factory=lambda: ['linux'])
	kernel_headers: bool = False
	init_hooks: InitHooks = InitHooks.Busybox
	disk_config: DiskLayoutConfiguration | None = None
	auth_config: AuthenticationConfiguration | None = None
	locale_config: LocaleConfiguration | None = None
	pacman_config: PacmanConfiguration | None = None
	swap: ZramConfiguration | None = None
	profile_config: ProfileConfiguration | None = None
	hostname: str = 'archlinux'
	app_config: ApplicationConfiguration | None = None
	network_config: NetworkConfiguration | None = None
	timezone: str | None = None
	ntp: bool = True
	packages: list[str] = field(default_factory=list)
	aur_packages: list[str] = field(default_factory=list)
	services: list[str | UserService] = field(default_factory=list)
	custom_commands: list[str] = field(
		default_factory=lambda: [
			'#arch-chroot via bash tmp files # lines are ignored',
			'#ex: su - user -c "bash ~/.stash/repo/install.sh"',
		]
	)

	def safe_json(self) -> dict[str, Any]:
		# Order matches global menu
		config: dict[str, Any] = {
			'bug_report_url': self.bug_report_url,
			'script': self.script,
			'archinstoo-language': self.archinstoo_language.json(),
			'bootloader_config': self.bootloader_config.json() if self.bootloader_config else None,
			'kernels': self.kernels,
			'kernel_headers': self.kernel_headers,
			'init_hooks': self.init_hooks.json(),
			'disk_config': self.disk_config.json() if self.disk_config else None,
			'auth_config': self.auth_config.json() if self.auth_config else None,
			'locale_config': self.locale_config.json() if self.locale_config else None,
			'pacman_config': self.pacman_config.json() if self.pacman_config else None,
			'swap': self.swap,
			'profile_config': self.profile_config.json() if self.profile_config else None,
			'hostname': self.hostname,
			'app_config': self.app_config.json() if self.app_config else None,
			'network_config': self.network_config.json() if self.network_config else None,
			'timezone': self.timezone,
			'ntp': self.ntp,
			'packages': self.packages,
			'aur_packages': self.aur_packages,
			'services': [s.json() if isinstance(s, UserService) else s for s in self.services],
			'custom_commands': self.custom_commands,
		}

		return config

	@classmethod
	def from_config(cls, args_config: dict[str, Any], args: Arguments) -> Self:
		arch_config = cls()

		_set_direct(
			arch_config,
			args_config,
			{
				'bug_report_url': 'bug_report_url',
				'script': 'script',
				'hostname': 'hostname',
				'timezone': 'timezone',
				'kernels': 'kernels',
				'packages': 'packages',
				'aur_packages': 'aur_packages',
				'custom_commands': 'custom_commands',
			},
		)

		# Parse services: strings stay as-is, dicts become UserService
		if raw_services := args_config.get('services'):
			arch_config.services = [UserService.parse_arg(s) if isinstance(s, dict) else s for s in raw_services]

		_set_parsed(
			arch_config,
			args_config,
			{
				'pacman_config': (PacmanConfiguration, 'parse_args'),
				'disk_config': (DiskLayoutConfiguration, 'parse_arg'),
				'profile_config': (ProfileConfiguration, 'parse_arg'),
				'auth_config': (AuthenticationConfiguration, 'parse_arg'),
				'app_config': (ApplicationConfiguration, 'parse_arg'),
				'network_config': (NetworkConfiguration, 'parse_arg'),
			},
		)

		# Special cases that don't fit the pattern
		if lang := args_config.get('archinstoo-language'):
			arch_config.archinstoo_language = translation_handler.get_language_by_name(lang)

		arch_config.locale_config = LocaleConfiguration.parse_arg(args_config)

		if bootloader := args_config.get('bootloader_config'):
			arch_config.bootloader_config = BootloaderConfiguration.parse_arg(bootloader, args.skip_boot)

		if (swap := args_config.get('swap')) is not None:
			arch_config.swap = ZramConfiguration.parse_arg(swap)

		arch_config.kernel_headers = args_config.get('kernel_headers', False)
		arch_config.ntp = args_config.get('ntp', True)

		if init_hooks := args_config.get('init_hooks'):
			arch_config.init_hooks = InitHooks(init_hooks)

		return arch_config


class ArchConfigHandler:
	def __init__(self) -> None:
		self._parser: ArgumentParser = self._define_arguments()
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
		return self.args.script or self.config.script

	def pass_args_to_subscript(self) -> None:
		sys.argv = [sys.argv[0]] + self._remaining

	def print_help(self) -> None:
		self._parser.print_help()

	def clean_up(self) -> None:
		for item in logger.directory.iterdir():
			if item.is_dir():
				shutil.rmtree(item)
			else:
				item.unlink()

	def _define_arguments(self) -> ArgumentParser:
		parser = ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter, add_help=False)
		parser.add_argument(
			'--script',
			nargs='?',
			default='guided',
			help='Script to run for installation',
			type=str,
		)
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
			'--dry-run',
			action='store_true',
			default=False,
			help='Generates a configuration file and then exits instead of performing an installation',
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
			'--advanced',
			action='store_true',
			default=False,
			help='Enabled advanced options',
		)
		parser.add_argument(
			'--clean',
			action='store_true',
			default=False,
			help='Clean up the log directory on exit',
		)

		return parser

	def _parse_args(self) -> Arguments:
		# Use parse_known_args to ignore unknown arguments (e.g., from pytest)
		argparse_args, self._remaining = self._parser.parse_known_args()

		args: Arguments = Arguments(**vars(argparse_args))

		return args

	def _parse_config(self) -> dict[str, Any]:
		config: dict[str, Any] = {}
		config_data: str | None = None

		if self._args.config is not None:
			config_data = self._read_file(self._args.config)
		elif self._args.config_url is not None:
			config_data = self._fetch_from_url(self._args.config_url)

		if config_data is not None:
			try:
				config.update(json.loads(config_data))

			except JSONDecodeError as e:
				warn(f'Malformed JSON at line {e.lineno}, column {e.colno}: {e.msg}')
				raise SystemExit(1)

		return self._cleanup_config(config)

	def _fetch_from_url(self, url: str) -> str:
		if urllib.parse.urlparse(url).scheme:
			try:
				req = Request(url, headers={'User-Agent': 'ArchInstoo'})
				with urlopen(req) as resp:
					return cast(str, resp.read().decode('utf-8'))
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


class _ArchConfigHandlerHolder:
	instance: ArchConfigHandler | None = None


def get_arch_config_handler() -> ArchConfigHandler:
	if _ArchConfigHandlerHolder.instance is None:
		_ArchConfigHandlerHolder.instance = ArchConfigHandler()
	return _ArchConfigHandlerHolder.instance
