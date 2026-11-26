import json
import sys
import urllib.error
import urllib.parse
from dataclasses import dataclass, field
from json import JSONDecodeError
from typing import TYPE_CHECKING, Any, Self, TypedDict
from urllib.request import Request, urlopen

if TYPE_CHECKING:
	from pathlib import Path

	from archinstoo.lib.models.applications import ApplicationSerialization
	from archinstoo.lib.models.authentication import AuthenticationSerialization
	from archinstoo.lib.models.bootloader import BootloaderConfigSerialization
	from archinstoo.lib.models.device import _DiskLayoutConfigurationSerialization
	from archinstoo.lib.models.firmware import FirmwareConfigSerialization
	from archinstoo.lib.models.localization import LocaleConfigSerialization
	from archinstoo.lib.models.mirrors import _PacmanConfigurationSerialization
	from archinstoo.lib.models.network import _NetworkConfigurationSerialization
	from archinstoo.lib.models.profile import ProfileConfigurationSerialization
	from archinstoo.lib.models.service import UserServiceSerialization
	from archinstoo.lib.models.swap import SwapConfigSerialization
	from archinstoo.lib.models.sysctl import SysctlConfigSerialization
	from archinstoo.lib.profile.config import ProfileConfiguration

from archinstoo.lib.cli import DEFAULT_SCRIPT, Arguments, build_parser
from archinstoo.lib.disk.device_handler import DeviceHandler
from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.localization.catalog import get_kb_layout
from archinstoo.lib.models.applications import ApplicationConfiguration
from archinstoo.lib.models.authentication import AuthenticationConfiguration
from archinstoo.lib.models.bootloader import BootloaderConfiguration
from archinstoo.lib.models.device import DiskLayoutConfiguration
from archinstoo.lib.models.firmware import FirmwareConfiguration
from archinstoo.lib.models.graphics import (
	GFX_CUSTOM_CHOICES,
	GfxDriver,
	GfxPackage,
)
from archinstoo.lib.models.kernel import DEFAULT_KERNEL
from archinstoo.lib.models.localization import LocaleConfiguration
from archinstoo.lib.models.mirrors import PacmanConfiguration
from archinstoo.lib.models.network import NetworkConfiguration
from archinstoo.lib.models.service import UserService
from archinstoo.lib.models.swap import SwapConfiguration
from archinstoo.lib.models.sysctl import SysctlConfiguration
from archinstoo.lib.output import debug, error, warn
from archinstoo.lib.profile.profiles_handler import ProfileHandler
from archinstoo.lib.serialize import strip_none


def _ignored(key: str, value: object) -> None:
	debug(f'Ignoring config key {key!r}: {value!r} is empty')


# the saved-config format: safe_json() writes it, from_config() and
# scripts/_resolve.py read it. total=False because from_config tolerates any key
# missing; None is an unset section, which serialize.jsonify drops from the file
class ArchConfigSerialization(TypedDict, total=False):
	bug_report_url: str
	script: str
	locale_config: LocaleConfigSerialization | None
	pacman_config: _PacmanConfigurationSerialization | None
	bootloader_config: BootloaderConfigSerialization | None
	disk_config: _DiskLayoutConfigurationSerialization | None
	swap: SwapConfigSerialization | None
	kernels: list[str]
	kernel_headers: bool
	firmware: FirmwareConfigSerialization
	profile_config: ProfileConfigurationSerialization | None
	gfx_driver: str | None
	gfx_packages: list[str]
	hostname: str
	auth_config: AuthenticationSerialization | None
	app_config: ApplicationSerialization | None
	network_config: _NetworkConfigurationSerialization | None
	timezone: str | None
	ntp: bool
	packages: list[str]
	aur_packages: list[str]
	services: list[str | UserServiceSerialization]
	sysctl: SysctlConfigSerialization | None
	custom_commands: list[str]


@dataclass
class ArchConfig:
	bug_report_url: str = 'https://github.com/h8d13/archinstoo'
	script: str = DEFAULT_SCRIPT  # label only, see ArchConfigHandler.get_script
	locale_config: LocaleConfiguration | None = None
	disk_config: DiskLayoutConfiguration | None = None
	profile_config: ProfileConfiguration | None = None
	gfx_driver: GfxDriver | None = None
	gfx_packages: list[GfxPackage] = field(default_factory=list)
	pacman_config: PacmanConfiguration | None = None
	network_config: NetworkConfiguration | None = None
	bootloader_config: BootloaderConfiguration | None = None
	app_config: ApplicationConfiguration | None = None
	auth_config: AuthenticationConfiguration | None = None
	swap: SwapConfiguration | None = None
	hostname: str = 'archlinux'
	kernels: list[str] = field(default_factory=lambda: [DEFAULT_KERNEL.value])
	kernel_headers: bool = False
	firmware: FirmwareConfiguration = field(
		default_factory=lambda: FirmwareConfiguration.default(SysInfo.is_vm())
	)
	ntp: bool = True
	packages: list[str] = field(default_factory=list)
	aur_packages: list[str] = field(default_factory=list)
	timezone: str | None = None
	services: list[str | UserService] = field(default_factory=list)
	sysctl: SysctlConfiguration | None = None
	custom_commands: list[str] = field(default_factory=list)

	def safe_json(self) -> ArchConfigSerialization:
		# Order matches global menu
		config: ArchConfigSerialization = {
			'bug_report_url': self.bug_report_url,
			'script': self.script,
			'locale_config': self.locale_config.json()
			if self.locale_config
			else None,
			'pacman_config': self.pacman_config.json()
			if self.pacman_config
			else None,
			'bootloader_config': self.bootloader_config.json()
			if self.bootloader_config
			else None,
			'disk_config': self.disk_config.json()
			if self.disk_config
			else None,
			'swap': self.swap.json() if self.swap else None,
			'kernels': self.kernels,
			'kernel_headers': self.kernel_headers,
			'firmware': self.firmware.json(),
			'profile_config': ProfileHandler().config_json(
				self.profile_config
			)
			if self.profile_config
			else None,
			'gfx_driver': self.gfx_driver.value
			if self.gfx_driver
			else None,
			'gfx_packages': [p.value for p in self.gfx_packages],
			'hostname': self.hostname,
			'auth_config': self.auth_config.json()
			if self.auth_config
			else None,
			'app_config': self.app_config.json()
			if self.app_config
			else None,
			'network_config': self.network_config.json()
			if self.network_config
			else None,
			'timezone': self.timezone,
			'ntp': self.ntp,
			'packages': self.packages,
			'aur_packages': self.aur_packages,
			'services': [
				s.json() if isinstance(s, UserService) else s
				for s in self.services
			],
			'sysctl': self.sysctl.json() if self.sysctl else None,
			'custom_commands': self.custom_commands,
		}
		return config

	@classmethod
	def from_config(cls, args_config: ArchConfigSerialization) -> Self:
		arch_config = cls()

		# subscripted, not .get(): mypy checks a looped key only that way
		for key in (
			'bug_report_url',
			'script',
			'hostname',
			'timezone',
			'kernels',
			'packages',
			'aur_packages',
			'custom_commands',
		):
			if key not in args_config:
				continue
			if value := args_config[key]:
				setattr(arch_config, key, value)
			else:
				_ignored(key, value)

		# a hand-written "packages": [""] reached pacman as an empty name
		arch_config.packages = [p for p in arch_config.packages if p]

		# Parse services: strings stay as-is, dicts become UserService
		if raw_services := args_config.get('services'):
			arch_config.services = [
				s if isinstance(s, str) else UserService.parse_arg(s)
				for s in raw_services
			]

		for section in (
			'pacman_config',
			'disk_config',
			'profile_config',
			'auth_config',
			'app_config',
			'network_config',
		):
			if section in args_config and not args_config[section]:
				_ignored(section, args_config[section])

		if pacman := args_config.get('pacman_config'):
			arch_config.pacman_config = PacmanConfiguration.parse_args(
				pacman
			)
		if disk := args_config.get('disk_config'):
			arch_config.disk_config = DiskLayoutConfiguration.parse_arg(
				disk, DeviceHandler()
			)
		if profile := args_config.get('profile_config'):
			arch_config.profile_config = ProfileHandler().parse_config(
				profile
			)
		if auth := args_config.get('auth_config'):
			arch_config.auth_config = AuthenticationConfiguration.parse_arg(
				auth
			)
		if app := args_config.get('app_config'):
			arch_config.app_config = ApplicationConfiguration.parse_arg(app)
		if network := args_config.get('network_config'):
			arch_config.network_config = NetworkConfiguration.parse_arg(
				network
			)

		# Special cases that don't fit the pattern
		arch_config.locale_config = LocaleConfiguration.parse_arg(
			args_config.get('locale_config') or {}, get_kb_layout()
		)

		if bootloader := args_config.get('bootloader_config'):
			arch_config.bootloader_config = (
				BootloaderConfiguration.parse_arg(bootloader)
			)

		if (swap := args_config.get('swap')) is not None:
			arch_config.swap = SwapConfiguration.parse_arg(swap)

		if (sysctl := args_config.get('sysctl')) is not None:
			arch_config.sysctl = SysctlConfiguration.parse_arg(sysctl)

		# subscripted: GfxDriver() takes any object, .get() any key
		if args_config.get('gfx_driver'):
			arch_config.gfx_driver = GfxDriver(args_config['gfx_driver'])
		# names outside the custom pool are dropped: unknown ones, and dkms
		# with its nvidia variant, which the kernel list decides. A list, as
		# an entry that is no name at all (a nested list) cannot be hashed
		pool = [p.value for p in GFX_CUSTOM_CHOICES]
		picked = args_config.get('gfx_packages') or []
		arch_config.gfx_packages = [GfxPackage(p) for p in picked if p in pool]
		if dropped := [p for p in picked if p not in pool]:
			debug(f'Ignoring gfx_packages {dropped!r}: not a custom choice')

		arch_config.kernel_headers = args_config.get('kernel_headers', False)
		if firmware := args_config.get('firmware'):
			arch_config.firmware = FirmwareConfiguration.parse_arg(firmware)
		arch_config.ntp = args_config.get('ntp', True)

		return arch_config


class ArchConfigHandler:
	def __init__(self) -> None:
		self._parser = build_parser()
		args: Arguments = self._parse_args()
		self._args = args

		config = self._parse_config()

		try:
			self._config = ArchConfig.from_config(config)
		except ValueError as err:
			warn(str(err))
			sys.exit(1)

	@property
	def config(self) -> ArchConfig:
		return self._config

	@config.setter
	def config(self, value: ArchConfig) -> None:
		self._config = value

	@property
	def args(self) -> Arguments:
		return self._args

	def get_script(self) -> str:
		# --script alone decides what runs. ArchConfig.script is a label written
		# into the saved JSON so resume knows what produced it, and --config-url
		# fetches that JSON remotely: a config must not pick the code path.
		return self.args.script or DEFAULT_SCRIPT

	def pass_args_to_subscript(self) -> None:
		sys.argv = [sys.argv[0], *self._remaining]

	def _parse_args(self) -> Arguments:
		# Use parse_known_args to ignore unknown arguments (e.g., from pytest)
		argparse_args, self._remaining = self._parser.parse_known_args()

		args: Arguments = Arguments(**vars(argparse_args))

		return args

	def _parse_config(self) -> ArchConfigSerialization:
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
				warn(
					f'Malformed JSON at line {e.lineno}, '
					f'column {e.colno}: {e.msg}'
				)
				raise SystemExit(1) from e

		# the JSON boundary: nothing checks the shape, from_config tolerates it
		cleaned: ArchConfigSerialization = strip_none(config)
		return cleaned

	def _fetch_from_url(self, url: str) -> str:
		if urllib.parse.urlparse(url).scheme in {'http', 'https'}:
			try:
				req = Request(url, headers={'User-Agent': 'ArchInstoo'})  # noqa: S310 - scheme restricted above
				with urlopen(req) as resp:  # noqa: S310 - scheme restricted above
					content: str = resp.read().decode('utf-8')
					return content
			except urllib.error.HTTPError as err:
				error(f'Could not fetch JSON from {url}: {err}')
		else:
			error('Not a valid url (only http/https allowed)')

		sys.exit(1)

	def _read_file(self, path: Path) -> str:
		if not path.exists():
			error(f'Could not find file {path}')
			sys.exit(1)

		return path.read_text()


class _ArchConfigHandlerHolder:
	instance: ArchConfigHandler | None = None


def get_arch_config_handler() -> ArchConfigHandler:
	if _ArchConfigHandlerHolder.instance is None:
		_ArchConfigHandlerHolder.instance = ArchConfigHandler()
	return _ArchConfigHandlerHolder.instance
