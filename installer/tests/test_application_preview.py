# One preview serves every application category: each holds a single field (a
# flag, a choice or a list of them), shown under the menu item's own label.

from archinstoo.lib.applications.application_menu import ApplicationMenu
from archinstoo.lib.models.applications import (
	ApplicationConfiguration,
	Audio,
	AudioConfiguration,
	BluetoothConfiguration,
	Management,
	ManagementConfiguration,
)


def test_preview_covers_flag_choice_and_list() -> None:
	tools = list(Management)[:2]
	menu = ApplicationMenu(
		ApplicationConfiguration(
			bluetooth_config=BluetoothConfiguration(enabled=True),
			audio_config=AudioConfiguration(audio=Audio.PIPEWIRE),
			management_config=ManagementConfiguration(tools=tools),
		)
	)

	lines = menu.preview_lines()

	assert lines == [
		'Bluetooth: Enabled',
		f'Audio: {Audio.PIPEWIRE.value}',
		f'Management: {", ".join(t.value for t in tools)}',
	]
