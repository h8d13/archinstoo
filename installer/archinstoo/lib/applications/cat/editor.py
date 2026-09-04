from typing import TYPE_CHECKING

from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.application import EditorConfiguration


class EditorApp:
	def install(
		self,
		install_session: Installer,
		editor_config: EditorConfiguration,
	) -> None:
		editor = editor_config.editor
		debug(f'Installing editor: {editor.value}')

		install_session.add_additional_packages(editor.packages)
		install_session.set_environment({'EDITOR': editor.binary})
