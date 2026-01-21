import datetime
import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, NotRequired, Self, TypedDict, override

from ..models.packages import Repository
from ..networking import DownloadTimer, fetch_data_from_url, ping
from ..output import debug


def _parse_datetime(value: str | datetime.datetime | None) -> datetime.datetime | None:
	"""Parse ISO datetime string, handling Z suffix and already-parsed values."""
	if value is None:
		return None
	if isinstance(value, datetime.datetime):
		return value
	try:
		return datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
	except (ValueError, AttributeError):
		return None


@dataclass
class MirrorStatusEntryV3:
	url: str
	protocol: str
	active: bool
	country: str
	country_code: str
	isos: bool
	ipv4: bool
	ipv6: bool
	details: str
	delay: int | None = None
	last_sync: datetime.datetime | None = None
	duration_avg: float | None = None
	duration_stddev: float | None = None
	completion_pct: float | None = None
	score: float | None = None
	_latency: float | None = field(default=None, repr=False)
	_speed: float | None = field(default=None, repr=False)
	_hostname: str | None = field(default=None, repr=False)
	_port: int | None = field(default=None, repr=False)
	_speedtest_retries: int | None = field(default=None, repr=False)

	def __post_init__(self) -> None:
		if self.score is not None:
			self.score = round(self.score)

		self._hostname, *port = urllib.parse.urlparse(self.url).netloc.split(':', 1)
		self._port = int(port[0]) if port else None

		debug(f'Loaded mirror {self._hostname}' + (f' with score {self.score}' if self.score else ''))

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> Self:
		return cls(
			url=data['url'],
			protocol=data['protocol'],
			active=data['active'],
			country=data['country'],
			country_code=data['country_code'],
			isos=data['isos'],
			ipv4=data['ipv4'],
			ipv6=data['ipv6'],
			details=data['details'],
			delay=data.get('delay'),
			last_sync=_parse_datetime(data.get('last_sync')),
			duration_avg=data.get('duration_avg'),
			duration_stddev=data.get('duration_stddev'),
			completion_pct=data.get('completion_pct'),
			score=data.get('score'),
		)

	@property
	def server_url(self) -> str:
		return f'{self.url}$repo/os/$arch'

	@property
	def speed(self) -> float:
		if self._speed is None:
			if not self._speedtest_retries:
				self._speedtest_retries = 3
			elif self._speedtest_retries < 1:
				self._speedtest_retries = 1

			retry = 0
			while retry < self._speedtest_retries and self._speed is None:
				debug(f'Checking download speed of {self._hostname}[{self.score}] by fetching: {self.url}core/os/x86_64/core.db')
				req = urllib.request.Request(url=f'{self.url}core/os/x86_64/core.db')

				try:
					with urllib.request.urlopen(req, None, 5) as handle, DownloadTimer(timeout=5) as timer:
						size = len(handle.read())

					assert timer.time is not None
					self._speed = size / timer.time
					debug(f'    speed: {self._speed} ({int(self._speed / 1024 / 1024 * 100) / 100}MiB/s)')
				# Do not retry error
				except urllib.error.URLError as error:
					debug(f'    speed: <undetermined> ({error}), skip')
					self._speed = 0
				# Do retry error
				except (http.client.IncompleteRead, ConnectionResetError) as error:
					debug(f'    speed: <undetermined> ({error}), retry')
				# Catch all
				except Exception as error:
					debug(f'    speed: <undetermined> ({error}), skip')
					self._speed = 0

				retry += 1

			if self._speed is None:
				self._speed = 0

		return self._speed

	@property
	def latency(self) -> float | None:
		if self._latency is None:
			debug(f'Checking latency for {self.url}')
			assert self._hostname is not None
			self._latency = ping(self._hostname, timeout=2)
			debug(f'  latency: {self._latency}')

		return self._latency


@dataclass
class MirrorStatusListV3:
	cutoff: int
	last_check: datetime.datetime
	num_checks: int
	urls: list[MirrorStatusEntryV3]
	version: int

	def __post_init__(self) -> None:
		if self.version != 3:
			raise ValueError('MirrorStatusListV3 only accepts version 3 data')

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> Self:
		if data.get('version') != 3:
			raise ValueError('MirrorStatusListV3 only accepts version 3 data')

		return cls(
			cutoff=data['cutoff'],
			last_check=_parse_datetime(data['last_check']) or datetime.datetime.now(datetime.UTC),
			num_checks=data['num_checks'],
			urls=[MirrorStatusEntryV3.from_dict(u) for u in data['urls']],
			version=data['version'],
		)

	@classmethod
	def from_json(cls, data: str) -> Self:
		return cls.from_dict(json.loads(data))

	def to_json(self) -> str:
		return json.dumps(
			{
				'cutoff': self.cutoff,
				'last_check': self.last_check.isoformat(),
				'num_checks': self.num_checks,
				'urls': [asdict(u) for u in self.urls],
				'version': self.version,
			}
		)


@dataclass
class ArchLinuxDeCountry:
	code: str
	name: str

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> Self:
		return cls(code=data['code'], name=data['name'])


@dataclass
class ArchLinuxDeMirrorEntry:
	url: str
	host: str
	country: ArchLinuxDeCountry | None = None
	durationAvg: float | None = None
	delay: int | None = None
	durationStddev: float | None = None
	completionPct: float | None = None
	score: float | None = None
	lastSync: datetime.datetime | None = None
	ipv4: bool = True
	ipv6: bool = False

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> Self:
		return cls(
			url=data['url'],
			host=data['host'],
			country=ArchLinuxDeCountry.from_dict(data['country']) if data.get('country') else None,
			durationAvg=data.get('durationAvg'),
			delay=data.get('delay'),
			durationStddev=data.get('durationStddev'),
			completionPct=data.get('completionPct'),
			score=data.get('score'),
			lastSync=_parse_datetime(data.get('lastSync')),
			ipv4=data.get('ipv4', True),
			ipv6=data.get('ipv6', False),
		)

	def to_v3_entry(self) -> dict[str, Any]:
		"""Convert to MirrorStatusEntryV3 compatible format"""
		return {
			'url': self.url,
			'protocol': urllib.parse.urlparse(self.url).scheme,
			'active': True,
			'country': self.country.name if self.country else 'Worldwide',
			'country_code': self.country.code if self.country else 'WW',
			'isos': True,
			'ipv4': self.ipv4,
			'ipv6': self.ipv6,
			'details': self.host,
			'delay': self.delay,
			'last_sync': self.lastSync,
			'duration_avg': self.durationAvg,
			'duration_stddev': self.durationStddev,
			'completion_pct': self.completionPct,
			'score': self.score,
		}


@dataclass
class ArchLinuxDeMirrorList:
	offset: int
	limit: int
	total: int
	count: int
	items: list[ArchLinuxDeMirrorEntry]

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> Self:
		return cls(
			offset=data['offset'],
			limit=data['limit'],
			total=data['total'],
			count=data['count'],
			items=[ArchLinuxDeMirrorEntry.from_dict(i) for i in data['items']],
		)

	@classmethod
	def from_json(cls, data: str) -> Self:
		return cls.from_dict(json.loads(data))

	@classmethod
	def fetch_all(cls, base_url: str) -> Self:
		"""Fetch all paginated results from archlinux.de API"""
		limit = 100
		first_page = cls.from_json(fetch_data_from_url(f'{base_url}?offset=0&limit={limit}'))
		all_items = list(first_page.items)

		for offset in range(limit, first_page.total, limit):
			page = cls.from_json(fetch_data_from_url(f'{base_url}?offset={offset}&limit={limit}'))
			all_items.extend(page.items)
			debug(f'Fetched {len(all_items)}/{first_page.total} mirrors')

		return cls(offset=0, limit=len(all_items), total=len(all_items), count=len(all_items), items=all_items)

	def to_v3(self) -> MirrorStatusListV3:
		"""Convert to MirrorStatusListV3 format"""
		urls = [item.to_v3_entry() for item in self.items]
		return MirrorStatusListV3.from_dict(
			{
				'version': 3,
				'cutoff': 3600,
				'last_check': datetime.datetime.now(datetime.UTC),
				'num_checks': 1,
				'urls': urls,
			}
		)


@dataclass
class MirrorRegion:
	name: str
	urls: list[str]

	def json(self) -> dict[str, list[str]]:
		return {self.name: self.urls}

	@override
	def __eq__(self, other: object) -> bool:
		if not isinstance(other, MirrorRegion):
			return NotImplemented
		return self.name == other.name


class SignCheck(Enum):
	Never = 'Never'
	Optional = 'Optional'
	Required = 'Required'


class SignOption(Enum):
	TrustedOnly = 'TrustedOnly'
	TrustAll = 'TrustAll'


class _CustomRepositorySerialization(TypedDict):
	name: str
	url: str
	sign_check: str
	sign_option: str


@dataclass
class CustomRepository:
	name: str
	url: str
	sign_check: SignCheck
	sign_option: SignOption

	def table_data(self) -> dict[str, str]:
		return {
			'Name': self.name,
			'Url': self.url,
			'Sign check': self.sign_check.value,
			'Sign options': self.sign_option.value,
		}

	def json(self) -> _CustomRepositorySerialization:
		return {
			'name': self.name,
			'url': self.url,
			'sign_check': self.sign_check.value,
			'sign_option': self.sign_option.value,
		}

	@classmethod
	def parse_args(cls, args: list[dict[str, str]]) -> list[Self]:
		configs = []
		for arg in args:
			configs.append(
				cls(
					arg['name'],
					arg['url'],
					SignCheck(arg['sign_check']),
					SignOption(arg['sign_option']),
				),
			)

		return configs


@dataclass
class CustomServer:
	url: str

	def table_data(self) -> dict[str, str]:
		return {'Url': self.url}

	def json(self) -> dict[str, str]:
		return {'url': self.url}

	@classmethod
	def parse_args(cls, args: list[dict[str, str]]) -> list[Self]:
		configs = []
		for arg in args:
			configs.append(
				cls(arg['url']),
			)

		return configs


class _PacmanConfigurationSerialization(TypedDict):
	mirror_regions: dict[str, list[str]]
	custom_servers: list[CustomServer]
	optional_repositories: list[str]
	custom_repositories: list[_CustomRepositorySerialization]
	pacman_options: NotRequired[list[str]]


# Available pacman.conf misc options
PACMAN_OPTIONS = ['Color', 'ILoveCandy', 'VerbosePkgLists']


@dataclass
class PacmanConfiguration:
	mirror_regions: list[MirrorRegion] = field(default_factory=list)
	custom_servers: list[CustomServer] = field(default_factory=list)
	optional_repositories: list[Repository] = field(default_factory=list)
	custom_repositories: list[CustomRepository] = field(default_factory=list)
	pacman_options: list[str] = field(default_factory=list)

	@property
	def region_names(self) -> str:
		return '\n'.join([m.name for m in self.mirror_regions])

	@property
	def custom_server_urls(self) -> str:
		return '\n'.join([s.url for s in self.custom_servers])

	def json(self) -> _PacmanConfigurationSerialization:
		regions = {}
		for m in self.mirror_regions:
			regions.update(m.json())

		config: _PacmanConfigurationSerialization = {
			'mirror_regions': regions,
			'custom_servers': self.custom_servers,
			'optional_repositories': [r.value for r in self.optional_repositories],
			'custom_repositories': [c.json() for c in self.custom_repositories],
		}

		if self.pacman_options:
			config['pacman_options'] = self.pacman_options

		return config

	def custom_servers_config(self) -> str:
		config = ''

		if self.custom_servers:
			config += '## Custom Servers\n'
			for server in self.custom_servers:
				config += f'Server = {server.url}\n'

		return config.strip()

	def regions_config(self, speed_sort: bool = True) -> str:
		from ..mirrors import mirror_list_handler

		config = ''

		for mirror_region in self.mirror_regions:
			sorted_stati = mirror_list_handler.get_status_by_region(
				mirror_region.name,
				speed_sort=speed_sort,
			)

			config += f'\n\n## {mirror_region.name}\n'

			for status in sorted_stati:
				config += f'Server = {status.server_url}\n'

		return config

	def repositories_config(self) -> str:
		config = ''

		for repo in self.custom_repositories:
			config += f'\n\n[{repo.name}]\n'
			config += f'SigLevel = {repo.sign_check.value} {repo.sign_option.value}\n'
			config += f'Server = {repo.url}\n'

		return config

	@classmethod
	def parse_args(
		cls,
		args: dict[str, Any],
	) -> Self:
		config = cls()

		if mirror_regions := args.get('mirror_regions', []):
			for region, urls in mirror_regions.items():
				config.mirror_regions.append(MirrorRegion(region, urls))

		if args.get('custom_servers'):
			config.custom_servers = CustomServer.parse_args(args['custom_servers'])

		# backwards compatibility with the new custom_repository
		if 'custom_mirrors' in args:
			config.custom_repositories = CustomRepository.parse_args(args['custom_mirrors'])
		if 'custom_repositories' in args:
			config.custom_repositories = CustomRepository.parse_args(args['custom_repositories'])

		if 'optional_repositories' in args:
			config.optional_repositories = [Repository(r) for r in args['optional_repositories']]

		if 'pacman_options' in args:
			config.pacman_options = args['pacman_options']

		return config
