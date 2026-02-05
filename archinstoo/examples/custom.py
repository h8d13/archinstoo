from typing import override

from archinstoo.default_profiles.desktop import DesktopProfile

# example custom profile

# this can extend an existing one or be full standalone

# see /examples/config-custom.json

# in this example we extend xfce
# for fully standalone you can just specify everything in this file and remove
# 'details' and 'custom_settings' from json file


class CustomDesktopProfile(DesktopProfile):
	def __init__(self) -> None:
		super().__init__()
		self.name = 'CustomDesktop'

	@property
	@override
	def packages(self) -> list[str]:
		return [
			'vlc',
			'neovim',
		]
