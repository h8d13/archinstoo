from enum import Enum

from archinstoo.lib.localization.catalog import list_timezones
from archinstoo.lib.tui.menu_item import MenuItem
from archinstoo.lib.tui.prompts import prompt_choice, prompt_text, prompt_yes_no


class PostInstallationAction(Enum):
	EXIT = 'exit archinstoo'
	REBOOT = 'reboot system'
	POWEROFF = 'poweroff system'
	CHROOT = 'chroot into install'


def select_ntp(preset: bool = True) -> bool:
	header = (
		'Would you like to use automatic time synchronization (NTP) with the '
		'default time servers?\n\n'
	)
	header += (
		'Hardware time and other post-configuration steps might be '
		'required in order for NTP to work.\n'
		'For more information, please check the Arch wiki\n'
	)

	choice = prompt_yes_no(header, preset)
	return preset if choice is None else choice


def select_hostname(preset: str | None = None) -> str | None:
	hostname = prompt_text('Hostname', preset=preset)
	if hostname is None:
		return preset
	return hostname or None


def select_timezone(preset: str | None = None) -> str | None:
	default = 'UTC'
	timezones = list_timezones()

	items = [MenuItem(tz, value=tz) for tz in timezones]
	return prompt_choice(
		items,
		preset,
		frame='Timezone',
		default=default,
		sort_items=True,
		allow_reset=True,
		reset=default,
	)


def select_post_installation(
	elapsed_time: float | None = None,
) -> PostInstallationAction:
	header = 'Installation completed'
	if elapsed_time is not None:
		minutes = int(elapsed_time // 60)
		seconds = int(elapsed_time % 60)
		header += f' in {minutes}m{seconds}s\n'
	header += 'What would you like to do next?\n'
	header += '\nAfter reboot, remove the installation medium\n'

	items = [
		MenuItem(action.value, value=action)
		for action in PostInstallationAction
	]
	return prompt_choice(items, header=header, allow_skip=False)
