from typing import TYPE_CHECKING

from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class MediaCodecsApp:
	@property
	def packages(self) -> list[str]:
		# the codec half of EndeavourOS' eos-base-group. gstreamer core, base
		# and good plus ffmpeg arrive as deps of these
		# https://github.com/endeavouros-team/EndeavourOS-packages-lists/blob/master/eos-base-group
		return [
			'gst-libav',
			'gst-plugins-bad',
			'gst-plugins-ugly',
			'gst-plugin-pipewire',
			'libdvdcss',
			'libopenraw',
		]

	def install(self, install_session: Installer) -> None:
		debug('Installing media codecs')
		install_session.add_additional_packages(self.packages)
