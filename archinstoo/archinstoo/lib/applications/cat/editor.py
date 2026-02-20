from typing import TYPE_CHECKING

from archinstoo.lib.models.application import Editor, EditorConfiguration
from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class EditorApp:
	def _get_editor_package(self, editor: Editor) -> str:
		# package names that differ from enum value
		return 'ex-vi-compat' if editor == Editor.VI else editor.value

	def _get_editor_binary(self, editor: Editor) -> str:
		# binary names that differ from enum value
		return 'nvim' if editor == Editor.NEOVIM else editor.value

	def install(
		self,
		install_session: Installer,
		editor_config: EditorConfiguration,
	) -> None:
		pkg = self._get_editor_package(editor_config.editor)
		debug(f'Installing editor: {pkg}')

		install_session.add_additional_packages([pkg])

		editor_binary = self._get_editor_binary(editor_config.editor)
		environment_path = install_session.target / 'etc' / 'environment'
		debug(f'Setting EDITOR={editor_binary} in {environment_path}')

		with open(environment_path, 'a') as f:
			f.write(f'EDITOR={editor_binary}\n')
