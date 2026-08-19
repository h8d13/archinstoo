from dataclasses import dataclass
from enum import StrEnum, auto
from typing import ClassVar, NotRequired, Self, TypedDict


class PowerManagement(StrEnum):
	PPD = 'power-profiles-daemon'
	TUNED = auto()


class PowerManagementConfigSerialization(TypedDict):
	power_management: str


class CPUScheduler(StrEnum):
	# values match scx_loader's scheduler names (binaries in scx-scheds)
	BEERLAND = 'scx_beerland'
	BPFLAND = 'scx_bpfland'
	CAKE = 'scx_cake'
	COSMOS = 'scx_cosmos'
	FLASH = 'scx_flash'
	FLOW = 'scx_flow'
	FORGE = 'scx_forge'
	LAVD = 'scx_lavd'
	P2DQ = 'scx_p2dq'
	PANDEMONIUM = 'scx_pandemonium'
	RUSTLAND = 'scx_rustland'
	RUSTY = 'scx_rusty'
	TICKLESS = 'scx_tickless'


# per upstream sched-ext/scx maturity table; rest are production-ready
EXPERIMENTAL_CPU_SCHEDULERS = frozenset(
	{
		CPUScheduler.CAKE,
		CPUScheduler.FLOW,
		CPUScheduler.FORGE,
		CPUScheduler.TICKLESS,
	}
)


class CPUSchedulerConfigSerialization(TypedDict):
	scheduler: str


class BluetoothConfigSerialization(TypedDict):
	enabled: bool


class Audio(StrEnum):
	PIPEWIRE = auto()
	PULSEAUDIO = auto()


class AudioConfigSerialization(TypedDict):
	audio: str


class PrintServiceConfigSerialization(TypedDict):
	enabled: bool


class Firewall(StrEnum):
	UFW = auto()
	FWD = 'firewalld'


class FirewallConfigSerialization(TypedDict):
	firewall: str


class Management(StrEnum):
	GIT = 'git'
	OPENSSH = 'openssh'
	WGET = 'wget'
	BASE_DEVEL = 'base-devel'
	MAN = 'man-db'
	PACMAN_CONTRIB = 'pacman-contrib'
	REFLECTOR = 'reflector'


class ManagementConfigSerialization(TypedDict):
	tools: list[str]


class Monitor(StrEnum):
	HTOP = auto()
	BTOP = auto()
	BOTTOM = auto()


class MonitorConfigSerialization(TypedDict):
	monitor: str


class Editor(StrEnum):
	VI = auto()
	NANO = auto()
	MICRO = auto()
	VIM = auto()
	NEOVIM = auto()
	EMACS = auto()


class EditorConfigSerialization(TypedDict):
	editor: str


class Security(StrEnum):
	APPARMOR = auto()
	FIREJAIL = auto()
	BUBBLEWRAP = auto()
	FAIL2BAN = auto()
	PAM_U2F = 'pam-u2f'
	SBCTL = auto()
	AUDIT = auto()


class SecurityConfigSerialization(TypedDict):
	tools: list[str]


class Language(StrEnum):
	RUSTUP = auto()
	GO = auto()
	JAVA = 'jdk-openjdk'
	NODEJS = auto()
	CLANG = auto()
	ZIG = auto()
	LUA = auto()


class LanguageConfigSerialization(TypedDict):
	tools: list[str]


# build + debug utilities, picked à la carte (one package per entry)
class DevTool(StrEnum):
	CMAKE = auto()
	MAKE = auto()
	NINJA = auto()
	MESON = auto()
	GDB = auto()
	LLVM = auto()
	LLD = auto()
	LLDB = auto()
	PERF = auto()
	STRACE = auto()
	LTRACE = auto()
	VALGRIND = auto()


class DevToolConfigSerialization(TypedDict):
	tools: list[str]


class DevelopmentConfigSerialization(TypedDict):
	language_config: NotRequired[LanguageConfigSerialization]
	devtool_config: NotRequired[DevToolConfigSerialization]


class ApplicationSerialization(TypedDict):
	bluetooth_config: NotRequired[BluetoothConfigSerialization]
	audio_config: NotRequired[AudioConfigSerialization]
	power_management_config: NotRequired[PowerManagementConfigSerialization]
	cpu_scheduler_config: NotRequired[CPUSchedulerConfigSerialization]
	print_service_config: NotRequired[PrintServiceConfigSerialization]
	firewall_config: NotRequired[FirewallConfigSerialization]
	management_config: NotRequired[ManagementConfigSerialization]
	monitor_config: NotRequired[MonitorConfigSerialization]
	editor_config: NotRequired[EditorConfigSerialization]
	security_config: NotRequired[SecurityConfigSerialization]
	development_config: NotRequired[DevelopmentConfigSerialization]


@dataclass
class AudioConfiguration:
	audio: Audio

	def json(self) -> AudioConfigSerialization:
		return {
			'audio': self.audio.value,
		}

	@classmethod
	def parse_arg(cls, arg: AudioConfigSerialization) -> Self:
		return cls(
			Audio(arg['audio']),
		)


@dataclass
class BluetoothConfiguration:
	enabled: bool

	def json(self) -> BluetoothConfigSerialization:
		return {'enabled': self.enabled}

	@classmethod
	def parse_arg(cls, arg: BluetoothConfigSerialization) -> Self:
		return cls(arg['enabled'])


@dataclass
class PowerManagementConfiguration:
	power_management: PowerManagement

	def json(self) -> PowerManagementConfigSerialization:
		return {
			'power_management': self.power_management.value,
		}

	@classmethod
	def parse_arg(cls, arg: PowerManagementConfigSerialization) -> Self:
		return cls(
			PowerManagement(arg['power_management']),
		)


@dataclass
class CPUSchedulerConfiguration:
	scheduler: CPUScheduler

	def json(self) -> CPUSchedulerConfigSerialization:
		return {
			'scheduler': self.scheduler.value,
		}

	@classmethod
	def parse_arg(cls, arg: CPUSchedulerConfigSerialization) -> Self:
		return cls(
			CPUScheduler(arg['scheduler']),
		)


@dataclass
class PrintServiceConfiguration:
	enabled: bool

	def json(self) -> PrintServiceConfigSerialization:
		return {'enabled': self.enabled}

	@classmethod
	def parse_arg(cls, arg: PrintServiceConfigSerialization) -> Self:
		return cls(arg['enabled'])


@dataclass
class FirewallConfiguration:
	firewall: Firewall

	def json(self) -> FirewallConfigSerialization:
		return {
			'firewall': self.firewall.value,
		}

	@classmethod
	def parse_arg(cls, arg: FirewallConfigSerialization) -> Self:
		return cls(
			Firewall(arg['firewall']),
		)


@dataclass
class ManagementConfiguration:
	tools: list[Management]

	def json(self) -> ManagementConfigSerialization:
		return {
			'tools': [t.value for t in self.tools],
		}

	@classmethod
	def parse_arg(cls, arg: ManagementConfigSerialization) -> Self:
		return cls(
			tools=[Management(t) for t in arg['tools']],
		)


@dataclass
class MonitorConfiguration:
	monitor: Monitor

	def json(self) -> MonitorConfigSerialization:
		return {
			'monitor': self.monitor.value,
		}

	@classmethod
	def parse_arg(cls, arg: MonitorConfigSerialization) -> Self:
		return cls(
			Monitor(arg['monitor']),
		)


@dataclass
class EditorConfiguration:
	editor: Editor

	def json(self) -> EditorConfigSerialization:
		return {
			'editor': self.editor.value,
		}

	@classmethod
	def parse_arg(cls, arg: EditorConfigSerialization) -> Self:
		return cls(
			Editor(arg['editor']),
		)


@dataclass
class SecurityConfiguration:
	tools: list[Security]

	def json(self) -> SecurityConfigSerialization:
		return {
			'tools': [t.value for t in self.tools],
		}

	@classmethod
	def parse_arg(cls, arg: SecurityConfigSerialization) -> Self:
		return cls(
			tools=[Security(t) for t in arg['tools']],
		)


@dataclass
class LanguageConfiguration:
	tools: list[Language]

	def json(self) -> LanguageConfigSerialization:
		return {
			'tools': [t.value for t in self.tools],
		}

	@classmethod
	def parse_arg(cls, arg: LanguageConfigSerialization) -> Self:
		return cls(
			tools=[Language(t) for t in arg['tools']],
		)


@dataclass
class DevToolConfiguration:
	tools: list[DevTool]

	def json(self) -> DevToolConfigSerialization:
		return {
			'tools': [t.value for t in self.tools],
		}

	@classmethod
	def parse_arg(cls, arg: DevToolConfigSerialization) -> Self:
		return cls(
			tools=[DevTool(t) for t in arg['tools']],
		)


@dataclass
class DevelopmentConfiguration:
	language_config: LanguageConfiguration | None = None
	devtool_config: DevToolConfiguration | None = None

	def json(self) -> DevelopmentConfigSerialization:
		out: DevelopmentConfigSerialization = {}
		if self.language_config:
			out['language_config'] = self.language_config.json()
		if self.devtool_config:
			out['devtool_config'] = self.devtool_config.json()
		return out

	@classmethod
	def parse_arg(cls, arg: DevelopmentConfigSerialization) -> Self:
		config = cls()
		if (lang := arg.get('language_config')) is not None:
			config.language_config = LanguageConfiguration.parse_arg(lang)
		if (devtool := arg.get('devtool_config')) is not None:
			config.devtool_config = DevToolConfiguration.parse_arg(devtool)
		return config


@dataclass
class ApplicationConfiguration:
	bluetooth_config: BluetoothConfiguration | None = None
	audio_config: AudioConfiguration | None = None
	power_management_config: PowerManagementConfiguration | None = None
	cpu_scheduler_config: CPUSchedulerConfiguration | None = None
	print_service_config: PrintServiceConfiguration | None = None
	firewall_config: FirewallConfiguration | None = None
	management_config: ManagementConfiguration | None = None
	monitor_config: MonitorConfiguration | None = None
	editor_config: EditorConfiguration | None = None
	security_config: SecurityConfiguration | None = None
	development_config: DevelopmentConfiguration | None = None

	_config_parsers: ClassVar[dict[str, type]] = {
		'bluetooth_config': BluetoothConfiguration,
		'audio_config': AudioConfiguration,
		'power_management_config': PowerManagementConfiguration,
		'cpu_scheduler_config': CPUSchedulerConfiguration,
		'print_service_config': PrintServiceConfiguration,
		'firewall_config': FirewallConfiguration,
		'management_config': ManagementConfiguration,
		'monitor_config': MonitorConfiguration,
		'editor_config': EditorConfiguration,
		'security_config': SecurityConfiguration,
		'development_config': DevelopmentConfiguration,
	}

	@classmethod
	def parse_arg(
		cls,
		args: ApplicationSerialization | None = None,
	) -> Self:
		app_config = cls()

		if args:
			for attr, parser_cls in cls._config_parsers.items():
				if (value := args.get(attr)) is not None:
					setattr(app_config, attr, parser_cls.parse_arg(value))  # type: ignore[attr-defined]
					# general rule of thumb if copy pasting more than 5x, abstract
					# dev can add to _config and to dataclass to import a new structure
					# then make the appropriate changes in applications/application_type.py
					# and archinstoo/lib/applications

		return app_config

	def json(self) -> ApplicationSerialization:
		return {attr: obj.json() for attr in self._config_parsers if (obj := getattr(self, attr))}  # type: ignore[return-value]
