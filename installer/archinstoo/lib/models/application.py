from dataclasses import dataclass, fields
from enum import Enum, StrEnum, auto
from typing import TYPE_CHECKING, Any, ClassVar, NotRequired, Self, TypedDict, get_args, get_origin

if TYPE_CHECKING:
	from collections.abc import Mapping


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


class ThunderboltConfigSerialization(TypedDict):
	enabled: bool


class Audio(StrEnum):
	PIPEWIRE = auto()
	PULSEAUDIO = auto()


class AudioConfigSerialization(TypedDict):
	audio: str


class PrintServiceConfigSerialization(TypedDict):
	enabled: bool


class MediaCodecsConfigSerialization(TypedDict):
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
	# modules-load.d entry so wine finds /dev/ntsync (kernels ship the module
	# but nothing autoloads it) docs.kernel.org/userspace-api/ntsync.html
	NTSYNC = 'ntsync-autoload'


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

	@property
	def packages(self) -> list[str]:
		# vi is provided by a differently named package
		return ['ex-vi-compat'] if self is Editor.VI else [self.value]

	@property
	def binary(self) -> str:
		# what lands in EDITOR= in /etc/environment
		return 'nvim' if self is Editor.NEOVIM else self.value


class EditorConfigSerialization(TypedDict):
	editor: str


class Terminal(StrEnum):
	ALACRITTY = auto()
	FOOT = auto()
	KITTY = auto()
	GHOSTTY = auto()
	KONSOLE = auto()
	WEZTERM = auto()
	XTERM = auto()

	@property
	def packages(self) -> list[str]:
		# package and binary share a name for every entry
		return [self.value]


DEFAULT_TERMINAL = Terminal.ALACRITTY.value


class TerminalConfigSerialization(TypedDict):
	terminal: str


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
	thunderbolt_config: NotRequired[ThunderboltConfigSerialization]
	audio_config: NotRequired[AudioConfigSerialization]
	power_management_config: NotRequired[PowerManagementConfigSerialization]
	cpu_scheduler_config: NotRequired[CPUSchedulerConfigSerialization]
	print_service_config: NotRequired[PrintServiceConfigSerialization]
	media_codecs_config: NotRequired[MediaCodecsConfigSerialization]
	firewall_config: NotRequired[FirewallConfigSerialization]
	management_config: NotRequired[ManagementConfigSerialization]
	monitor_config: NotRequired[MonitorConfigSerialization]
	editor_config: NotRequired[EditorConfigSerialization]
	terminal_config: NotRequired[TerminalConfigSerialization]
	security_config: NotRequired[SecurityConfigSerialization]
	development_config: NotRequired[DevelopmentConfigSerialization]


@dataclass
class _Category:
	# one dataclass field: an enum, a bool, or a list of enums. json() and
	# parse_arg() read it off the field, so a category is its declaration
	def json(self) -> dict[str, Any]:
		((name, value),) = vars(self).items()
		if isinstance(value, list):
			return {name: [v.value for v in value]}
		return {name: value.value if isinstance(value, Enum) else value}

	@classmethod
	def parse_arg(cls, arg: Mapping[str, Any]) -> Self:
		(spec,) = fields(cls)
		raw = arg[spec.name]
		if get_origin(spec.type) is list:
			(member,) = get_args(spec.type)
			return cls(**{spec.name: [member(v) for v in raw]})
		if isinstance(spec.type, type) and issubclass(spec.type, Enum):
			return cls(**{spec.name: spec.type(raw)})
		return cls(**{spec.name: raw})


@dataclass
class AudioConfiguration(_Category):
	audio: Audio


@dataclass
class BluetoothConfiguration(_Category):
	enabled: bool


@dataclass
class ThunderboltConfiguration(_Category):
	enabled: bool


@dataclass
class PowerManagementConfiguration(_Category):
	power_management: PowerManagement


@dataclass
class CPUSchedulerConfiguration(_Category):
	scheduler: CPUScheduler


@dataclass
class PrintServiceConfiguration(_Category):
	enabled: bool


@dataclass
class MediaCodecsConfiguration(_Category):
	enabled: bool


@dataclass
class FirewallConfiguration(_Category):
	firewall: Firewall


@dataclass
class ManagementConfiguration(_Category):
	tools: list[Management]


@dataclass
class MonitorConfiguration(_Category):
	monitor: Monitor


@dataclass
class EditorConfiguration(_Category):
	editor: Editor


@dataclass
class TerminalConfiguration(_Category):
	terminal: Terminal


@dataclass
class SecurityConfiguration(_Category):
	tools: list[Security]


@dataclass
class LanguageConfiguration(_Category):
	tools: list[Language]


@dataclass
class DevToolConfiguration(_Category):
	tools: list[DevTool]


@dataclass
class DevelopmentConfiguration:
	language_config: LanguageConfiguration | None = None
	devtool_config: DevToolConfiguration | None = None

	def json(self) -> dict[str, Any]:
		out: dict[str, Any] = {}
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
	thunderbolt_config: ThunderboltConfiguration | None = None
	audio_config: AudioConfiguration | None = None
	power_management_config: PowerManagementConfiguration | None = None
	cpu_scheduler_config: CPUSchedulerConfiguration | None = None
	print_service_config: PrintServiceConfiguration | None = None
	media_codecs_config: MediaCodecsConfiguration | None = None
	firewall_config: FirewallConfiguration | None = None
	management_config: ManagementConfiguration | None = None
	monitor_config: MonitorConfiguration | None = None
	editor_config: EditorConfiguration | None = None
	terminal_config: TerminalConfiguration | None = None
	security_config: SecurityConfiguration | None = None
	development_config: DevelopmentConfiguration | None = None

	# category -> its class, read off the fields below the class body
	_config_parsers: ClassVar[dict[str, type]]

	@property
	def terminal_command(self) -> str:
		if self.terminal_config:
			return self.terminal_config.terminal.value
		return DEFAULT_TERMINAL

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
					# a new category is a field here and in ApplicationSerialization;
					# the rest of the flow is in .github/API_REF.md, "Add an application"

		return app_config

	def json(self) -> ApplicationSerialization:
		return {attr: obj.json() for attr in self._config_parsers if (obj := getattr(self, attr))}  # type: ignore[return-value]


# every field is `<Category>Configuration | None`; the class is the first arm
ApplicationConfiguration._config_parsers = {f.name: get_args(f.type)[0] for f in fields(ApplicationConfiguration)}


def terminal_for(app_config: ApplicationConfiguration | None) -> str:
	# a skipped application menu still has to leave keybind-only profiles a terminal
	return app_config.terminal_command if app_config else DEFAULT_TERMINAL
