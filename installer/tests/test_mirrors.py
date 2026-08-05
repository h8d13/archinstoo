import datetime
import json

from archinstoo.lib.models.mirrors import MirrorStatusListV3

# Minimal slice of archlinux.org/mirrors/status/json/ (version 3)
_ORG_JSON = json.dumps(
	{
		'cutoff': 86400,
		'last_check': '2026-06-08T10:00:00Z',
		'num_checks': 1,
		'version': 3,
		'urls': [
			{
				'url': 'https://mirror.example.org/archlinux/',
				'protocol': 'https',
				'active': True,
				'country': 'Germany',
				'country_code': 'DE',
				'isos': True,
				'ipv4': True,
				'ipv6': False,
				'details': 'https://mirror.example.org/',
				'delay': 1200,
				'last_sync': '2026-06-08T09:30:00Z',
				'duration_avg': 0.5,
				'duration_stddev': 0.1,
				'completion_pct': 1.0,
				'score': 1.7,
			},
		],
	}
)


def test_mirror_status_v3_from_json() -> None:
	status = MirrorStatusListV3.from_json(_ORG_JSON)

	assert status.version == 3
	assert len(status.urls) == 1

	entry = status.urls[0]
	assert entry.url == 'https://mirror.example.org/archlinux/'
	assert entry.country_code == 'DE'
	# score is rounded in __post_init__
	assert entry.score == 2
	# ISO strings are parsed into datetimes at the boundary
	assert isinstance(entry.last_sync, datetime.datetime)
