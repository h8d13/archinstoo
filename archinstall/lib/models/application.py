from dataclasses import dataclass
from enum import StrEnum, auto
from typing import NotRequired, Self, TypedDict


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

	@classmethod
	def parse_arg(
		cls,
		args: ApplicationSerialization | None = None,
	) -> Self:
		app_config = cls()

		if args and (bluetooth_config := args.get('bluetooth_config')) is not None:
			app_config.bluetooth_config = BluetoothConfiguration.parse_arg(bluetooth_config)

		if args and (audio_config := args.get('audio_config')) is not None:
			app_config.audio_config = AudioConfiguration.parse_arg(audio_config)

		if args and (power_management_config := args.get('power_management_config')) is not None:
			app_config.power_management_config = PowerManagementConfiguration.parse_arg(power_management_config)

		if args and (print_service_config := args.get('print_service_config')) is not None:
			app_config.print_service_config = PrintServiceConfiguration.parse_arg(print_service_config)

		if args and (firewall_config := args.get('firewall_config')) is not None:
			app_config.firewall_config = FirewallConfiguration.parse_arg(firewall_config)

		if args and (management_config := args.get('management_config')) is not None:
			app_config.management_config = ManagementConfiguration.parse_arg(management_config)

		if args and (monitor_config := args.get('monitor_config')) is not None:
			app_config.monitor_config = MonitorConfiguration.parse_arg(monitor_config)

		if args and (editor_config := args.get('editor_config')) is not None:
			app_config.editor_config = EditorConfiguration.parse_arg(editor_config)

		return app_config

	def json(self) -> ApplicationSerialization:
		config: ApplicationSerialization = {}

		if self.bluetooth_config:
			config['bluetooth_config'] = self.bluetooth_config.json()

		if self.audio_config:
			config['audio_config'] = self.audio_config.json()

		if self.power_management_config:
			config['power_management_config'] = self.power_management_config.json()

		if self.print_service_config:
			config['print_service_config'] = self.print_service_config.json()

		if self.firewall_config:
			config['firewall_config'] = self.firewall_config.json()

		if self.management_config:
			config['management_config'] = self.management_config.json()

		if self.monitor_config:
			config['monitor_config'] = self.monitor_config.json()

		if self.editor_config:
			config['editor_config'] = self.editor_config.json()

		return config
