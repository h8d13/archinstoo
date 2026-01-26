from archinstall.default_profiles.desktop import DesktopProfile
from archinstall.default_profiles.profile import Profile

# example custom profile

# this can extend an existing one or be full standalone

# see archinstoo/examples/config-custom.json
# in this example we extend xfce

# for fully standalone you can just specify everything in this file and remove 
# 'details' and 'custom_settings' from json

class CustomDesktopProfile(DesktopProfile):
	def __init__(self, current_selection: list[Profile] = []) -> None:
		super().__init__(current_selection)
		self.name = 'CustomDesktop'

	@property
	def packages(self) -> list[str]:
			return [
					'vlc',
					'neovim',
			]