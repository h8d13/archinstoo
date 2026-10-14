# greetd's front-ends replace the stock config.toml; the session runs as the
# account Fedora's greetd package creates, not Arch's 'greeter'

from types import SimpleNamespace
from typing import TYPE_CHECKING

from archinstoo.lib.profile.base import GreeterType
from archinstoo.lib.profile.profiles_handler import GREETD_USER, ProfileHandler

if TYPE_CHECKING:
	from pathlib import Path


def test_tuigreet_runs_as_the_packaged_user(tmp_path: Path) -> None:
	(tmp_path / 'etc/greetd').mkdir(parents=True)
	session = SimpleNamespace(
		target=tmp_path,
		add_additional_packages=lambda pkgs: None,
		enable_service=lambda services: None,
		disable_service=lambda services: None,
	)
	ProfileHandler().install_greeter(session, GreeterType.Tuigreet)  # type: ignore[arg-type]

	config = (tmp_path / 'etc/greetd/config.toml').read_text()
	assert GREETD_USER == 'greetd'
	assert f'user = "{GREETD_USER}"' in config
	assert 'command = "tuigreet ' in config
