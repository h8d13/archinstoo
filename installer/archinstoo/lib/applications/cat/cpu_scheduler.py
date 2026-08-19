from typing import TYPE_CHECKING

from archinstoo.lib.output import debug

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.application import CPUSchedulerConfiguration


class CPUSchedulerApp:
	@property
	def packages(self) -> list[str]:
		return [
			'scx-scheds',
			'scx-tools',
		]

	@property
	def services(self) -> list[str]:
		return [
			'scx_loader',
		]

	def install(
		self,
		install_session: Installer,
		cpu_scheduler_config: CPUSchedulerConfiguration,
	) -> None:
		debug(f'Installing sched_ext CPU scheduler: {cpu_scheduler_config.scheduler.value}')

		install_session.add_additional_packages(self.packages)

		# scx_loader (scx-tools) starts the scheduler at boot; sched_ext runs
		# as userspace BPF so no initramfs/mkinitcpio involvement
		config_dir = install_session.target / 'etc/scx_loader'
		config_dir.mkdir(parents=True, exist_ok=True)
		(config_dir / 'config.toml').write_text(f'default_sched = "{cpu_scheduler_config.scheduler.value}"\ndefault_mode = "Auto"\n')

		install_session.enable_service(self.services)
