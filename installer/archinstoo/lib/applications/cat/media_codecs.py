from typing import TYPE_CHECKING

from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer


class MediaCodecsApp:
	@property
	def packages(self) -> list[str]:
		# what Fedora's own repos carry: the -free builds and ffmpeg-free's
		# libav. Patent-encumbered codecs (and libdvdcss) are RPM Fusion's
		return [
			'gstreamer1-plugin-libav',
			'gstreamer1-plugins-bad-free',
			'gstreamer1-plugins-ugly-free',
			'pipewire-gstreamer',
			'libopenraw',
		]

	def install(self, install_session: Installer) -> None:
		debug('Installing media codecs')
		install_session.add_additional_packages(self.packages)
