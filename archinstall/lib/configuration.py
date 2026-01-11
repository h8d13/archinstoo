import json
import stat
from pathlib import Path
from typing import Any

from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import SelectMenu, Tui
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.types import Alignment, FrameProperties, Orientation, PreviewStyle

from .args import ArchConfig
from .general import JSON, UNSAFE_JSON
from .output import debug, info, logger, warn


class ConfigurationHandler:
	_USER_CONFIG_FILENAME = 'user_configuration.json'
	_USER_CREDS_FILENAME = 'user_credentials.json'

	def __init__(self, config: ArchConfig):
		"""
		Configuration output handler to parse the existing
		configuration data structure and prepare for output on the
		console and for saving it to configuration files

		:param config: Archinstall configuration object
		:type config: ArchConfig
		"""

		self._config = config
		self._default_save_path = logger.directory
		self._user_config_file = Path(self._USER_CONFIG_FILENAME)
		self._user_creds_file = Path(self._USER_CREDS_FILENAME)

	@property
	def user_configuration_file(self) -> Path:
		return self._user_config_file

	@property
	def user_credentials_file(self) -> Path:
		return self._user_creds_file

	def user_config_to_json(self) -> str:
		out = self._config.safe_json()
		return json.dumps(out, indent=4, sort_keys=True, cls=JSON)

	def user_credentials_to_json(self) -> str:
		out = self._config.unsafe_json()
		return json.dumps(out, indent=4, sort_keys=True, cls=UNSAFE_JSON)

	def write_debug(self) -> None:
		debug(' -- Chosen configuration --')
		debug(self.user_config_to_json())

	def confirm_config(self) -> bool:
		header = f'{tr("The specified configuration will be applied")}. '
		header += tr('Would you like to continue?') + '\n'

		with Tui():
			group = MenuItemGroup.yes_no()
			group.focus_item = MenuItem.yes()
			group.set_preview_for_all(lambda x: self.user_config_to_json())

			result = SelectMenu[bool](
				group,
				header=header,
				alignment=Alignment.CENTER,
				columns=2,
				orientation=Orientation.HORIZONTAL,
				allow_skip=False,
				preview_size='auto',
				preview_style=PreviewStyle.BOTTOM,
				preview_frame=FrameProperties.max(tr('Configuration')),
			).run()

			if result.item() != MenuItem.yes():
				return False

		return True

	def _save_file(self, path: Path, content: str) -> None:
		path.write_text(content)
		path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
		info(f'Saved {path}')

	def save(self, dest_path: Path | None = None) -> bool:
		save_path = dest_path or self._default_save_path

		try:
			save_path.mkdir(exist_ok=True, parents=True)

			self._save_file(save_path / self._user_config_file, self.user_config_to_json())
			self._save_file(save_path / self._user_creds_file, self.user_credentials_to_json())

			return True
		except Exception as e:
			warn(f'Failed to save config: {e}')
			return False

	@classmethod
	def has_saved_config(cls) -> bool:
		config_file = logger.directory / cls._USER_CONFIG_FILENAME
		return config_file.exists()

	@classmethod
	def load_saved_config(cls) -> dict[str, Any] | None:
		try:
			config_data: dict[str, Any] = {}

			# Load main config
			config_file = logger.directory / cls._USER_CONFIG_FILENAME
			if config_file.exists():
				with open(config_file) as f:
					config_data.update(json.load(f))

			# Load credentials
			creds_file = logger.directory / cls._USER_CREDS_FILENAME
			if creds_file.exists():
				with open(creds_file) as f:
					creds_data = json.load(f)
					config_data.update(creds_data)

			return config_data if config_data else None

		except Exception as e:
			warn(f'Failed to load saved config: {e}')
		return None

	@classmethod
	def delete_saved_config(cls) -> None:
		config_file = logger.directory / cls._USER_CONFIG_FILENAME
		creds_file = logger.directory / cls._USER_CREDS_FILENAME
		if config_file.exists():
			config_file.unlink()
			info(f'Deleted {config_file}')
		if creds_file.exists():
			creds_file.unlink()
			info(f'Deleted {creds_file}')
