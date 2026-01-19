from dataclasses import dataclass
from enum import StrEnum, auto
from typing import ClassVar, NotRequired, Self, TypedDict


class PowerManagement(StrEnum):
	PPD = 'power-profiles-daemon'
	TUNED = 'tuned'


class PowerManagementConfigSerialization(TypedDict):
	power_management: str


class BluetoothConfigSerialization(TypedDict):
	enabled: bool


class Audio(StrEnum):
	NO_AUDIO = 'No audio server'
	PIPEWIRE = auto()
	PULSEAUDIO = auto()


class AudioConfigSerialization(TypedDict):
	audio: str


class PrintServiceConfigSerialization(TypedDict):
	enabled: bool


class Firewall(StrEnum):
	UFW = 'ufw'
	FWD = 'firewalld'


class FirewallConfigSerialization(TypedDict):
	firewall: str


class Management(StrEnum):
	GIT = 'git'
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
	NANO = auto()
	MICRO = auto()
	VI = auto()
	VIM = auto()
	NEOVIM = auto()
	EMACS = auto()


class EditorConfigSerialization(TypedDict):
	editor: str


class ZramAlgorithm(StrEnum):
	ZSTD = 'zstd'
	LZO_RLE = 'lzo-rle'
	LZO = 'lzo'
	LZ4 = 'lz4'
	LZ4HC = 'lz4hc'


class ZramConfigSerialization(TypedDict):
	enabled: bool
	algorithm: NotRequired[str]


class ApplicationSerialization(TypedDict):
	bluetooth_config: NotRequired[BluetoothConfigSerialization]
	audio_config: NotRequired[AudioConfigSerialization]
	power_management_config: NotRequired[PowerManagementConfigSerialization]
	print_service_config: NotRequired[PrintServiceConfigSerialization]
	firewall_config: NotRequired[FirewallConfigSerialization]
	management_config: NotRequired[ManagementConfigSerialization]
	monitor_config: NotRequired[MonitorConfigSerialization]
	editor_config: NotRequired[EditorConfigSerialization]


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


@dataclass(frozen=True)
class ZramConfiguration:
	enabled: bool
	algorithm: ZramAlgorithm = ZramAlgorithm.ZSTD

	@classmethod
	def parse_arg(cls, arg: bool | ZramConfigSerialization) -> Self:
		if isinstance(arg, bool):
			return cls(enabled=arg)

		enabled = arg.get('enabled', True)
		algo = arg.get('algorithm', ZramAlgorithm.ZSTD.value)
		return cls(enabled=enabled, algorithm=ZramAlgorithm(algo))


@dataclass
class ApplicationConfiguration:
	bluetooth_config: BluetoothConfiguration | None = None
	audio_config: AudioConfiguration | None = None
	power_management_config: PowerManagementConfiguration | None = None
	print_service_config: PrintServiceConfiguration | None = None
	firewall_config: FirewallConfiguration | None = None
	management_config: ManagementConfiguration | None = None
	monitor_config: MonitorConfiguration | None = None
	editor_config: EditorConfiguration | None = None

	_config_parsers: ClassVar[dict[str, type]] = {
		'bluetooth_config': BluetoothConfiguration,
		'audio_config': AudioConfiguration,
		'power_management_config': PowerManagementConfiguration,
		'print_service_config': PrintServiceConfiguration,
		'firewall_config': FirewallConfiguration,
		'management_config': ManagementConfiguration,
		'monitor_config': MonitorConfiguration,
		'editor_config': EditorConfiguration,
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
					# and archinstall/lib/applications

		return app_config

	def json(self) -> ApplicationSerialization:
		return {attr: obj.json() for attr in self._config_parsers if (obj := getattr(self, attr))}  # type: ignore[return-value]
