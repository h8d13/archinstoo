import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import ServiceError, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.models.service import UserService
from archinstoo.lib.output import info
from archinstoo.lib.utils.env import Os

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer

# two sides: probes that ask the running system, and unit toggles on the
# target that take the Installer for chroot


def accessibility_tools_in_use() -> bool:
	# espeakup is a live-ISO accessibility unit. In a chroot systemctl
	# answers is-active with "Running in chroot, ignoring command" and
	# exit 0, which would read as active
	if not Os.has_systemd():
		return False

	try:
		SysCommand(
			'systemctl is-active --quiet espeakup.service',
			environment_vars={'SYSTEMD_COLORS': '0'},
		)
	except SysCallError:
		# nonzero: unit inactive, or absent on this host
		return False

	return True


def _systemctl_target(installation: Installer, action: str, service: str) -> None:
	# host systemctl drives the target offline via --root=. A non-systemd
	# host (alpine, ...) has no systemctl binary, so run the target's own
	# systemctl inside the chroot instead. enable/disable only write unit
	# symlinks, so they work without a running pid1 in the chroot.
	# https://docs.fedoraproject.org/en-US/quick-docs/systemd-understanding-and-administering/#_mapping_service_commands
	if shutil.which('systemctl'):
		SysCommand(f'systemctl --root={installation.target} {action} {service}')
	else:
		installation.arch_chroot(f'systemctl {action} {service}')


def enable_service(installation: Installer, services: str | list[str]) -> None:
	if isinstance(services, str):
		services = [services]

	for service in services:
		info(f'Enabling service {service}')

		try:
			_systemctl_target(installation, 'enable', service)
		except SysCallError as err:
			raise ServiceError(f'Unable to start service {service}: {err}') from err


def _enable_linger(installation: Installer, user: str) -> None:
	linger_dir = installation.target / 'var/lib/systemd/linger'
	linger_dir.mkdir(parents=True, exist_ok=True)
	(linger_dir / user).touch()
	info(f'Enabled linger for user {user}')


def _enable_user_service(installation: Installer, user: str, services: str | list[str]) -> None:
	if isinstance(services, str):
		services = [services]

	# what `systemctl --user enable` leaves for WantedBy=default.target
	# https://docs.fedoraproject.org/en-US/quick-docs/systemd-understanding-and-administering/#_install_parameters
	wants_dir = installation.target / f'home/{user}/.config/systemd/user/default.target.wants'
	wants_dir.mkdir(parents=True, exist_ok=True)

	for service in services:
		info(f'Enabling user service {service} for {user}')
		unit_path = Path(f'/usr/lib/systemd/user/{service}')
		symlink = wants_dir / service
		if not symlink.exists():
			symlink.symlink_to(unit_path)

	installation.chown_tree(user, f'/home/{user}/.config')


def enable_services_from_config(installation: Installer, services: list[str | UserService]) -> None:
	system_services = [s for s in services if isinstance(s, str)]
	user_services = [s for s in services if isinstance(s, UserService)]

	if system_services:
		enable_service(installation, system_services)

	for us in user_services:
		_enable_user_service(installation, us.user, us.unit)
		if us.linger:
			_enable_linger(installation, us.user)


def disable_service(installation: Installer, services_disable: str | list[str]) -> None:
	if isinstance(services_disable, str):
		services_disable = [services_disable]

	for service in services_disable:
		info(f'Disabling service {service}')

		try:
			_systemctl_target(installation, 'disable', service)
		except SysCallError as err:
			raise ServiceError(f'Unable to disable service {service}: {err}') from err
