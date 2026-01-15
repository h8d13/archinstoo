import json
import stat
from pathlib import Path
from typing import Any

from archinstall.lib.translationhandler import tr
from archinstall.tui.curses_menu import SelectMenu, Tui
from archinstall.tui.menu_item import MenuItem, MenuItemGroup
from archinstall.tui.types import Alignment, FrameProperties, Orientation, PreviewStyle

from .args import ArchConfig
from .general import JSON
from .output import debug, info, logger, warn


class ConfigurationHandler:
	_USER_CONFIG_FILENAME = 'user_configuration.json'

	def __init__(self, config: ArchConfig):
		"""
		Consolidated into one file

		:param config: Archinstall configuration object
		:type config: ArchConfig
		"""

		self._config = config

	@classmethod
	def _saved_config_path(cls) -> Path:
		return logger.directory / cls._USER_CONFIG_FILENAME

	def user_config_to_json(self) -> str:
		out = self._config.safe_json()
		return json.dumps(out, indent=4, cls=JSON)  # Note remove the sort so that we keep "menu order"

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

	def save(self) -> bool:
		try:
			config_file = self._saved_config_path()
			config_file.parent.mkdir(exist_ok=True, parents=True)
			self._save_file(config_file, self.user_config_to_json())
			return True
		except Exception as e:
			warn(f'Failed to save config: {e}')
			return False

	@classmethod
	def has_saved_config(cls) -> bool:
		return cls._saved_config_path().exists()

	@classmethod
	def load_saved_config(cls) -> dict[str, Any] | None:
		config_file = cls._saved_config_path()
		try:
			if config_file.exists():
				with open(config_file) as f:
					return json.load(f)
		except Exception as e:
			warn(f'Failed to load saved config: {e}')
		return None

	@classmethod
	def delete_saved_config(cls) -> None:
		config_file = cls._saved_config_path()
		if config_file.exists():
			config_file.unlink()
