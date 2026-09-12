import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import ServiceError, SysCallError
from archinstoo.lib.general import SysCommand
from archinstoo.lib.hardware import SysInfo
from archinstoo.lib.models.service import UserService
from archinstoo.lib.output import debug, info, warn
from archinstoo.lib.utils.env import Os

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer

# two sides: probes that ask the running system (live ISO or an installed
# host), and unit toggles on the target that take the Installer for chroot

_UNIT_SUFFIXES = ('.service', '.target', '.timer')


def _unit(service_name: str) -> str:
	if Path(service_name).suffix not in _UNIT_SUFFIXES:
		service_name += '.service'  # Just to be safe
	return service_name


def _service_started(service_name: str) -> str | None:
	if not shutil.which('systemctl'):
		# non-systemd host has no unit to have started
		return None

	last_execution_time = (
		SysCommand(
			f'systemctl show --property=ActiveEnterTimestamp --no-pager {_unit(service_name)}',
			environment_vars={'SYSTEMD_COLORS': '0'},
		)
		.decode()
		.removeprefix('ActiveEnterTimestamp=')
	)

	return last_execution_time or None


def _service_state(service_name: str) -> str:
	if not shutil.which('systemctl'):
		# non-systemd host: nothing to poll, report inert so waits exit
		return 'dead'

	return SysCommand(
		f'systemctl show --no-pager -p SubState --value {_unit(service_name)}',
		environment_vars={'SYSTEMD_COLORS': '0'},
	).decode()


def accessibility_tools_in_use() -> bool:
	# espeakup is a live-ISO accessibility unit; a non-systemd host has neither
	# the binary nor the unit, so report not-in-use instead of crashing
	if not shutil.which('systemctl'):
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


def wait_iso_services(skip_ntp: bool, skip_wkd: bool) -> None:
	# Check for essential services statuses based on
	# architecture and parse results for prints
	# https://github.com/archlinux/archinstall/issues/3688
	# be more descriptive about status in code + what user sees
	if Os.running_from_host():
		# NTP/keyring-wkd-sync are live-ISO startup units: archiso boots
		# with an untrusted RTC and an empty trustdb and starts both. An
		# installed host runs whatever it runs; an idle timesyncd there
		# (networkd reporting offline, chrony instead, nothing) is not a
		# sign the clock is wrong, and pacman fails loudly if it is.
		debug('Running from host, skipping ISO service-stop checks')
		return

	if not skip_ntp:
		info('Waiting for NTP time synchronization...')

		# a stalled timesyncd (no route, blocked UDP 123) would otherwise
		# hold the install forever; keyring and TLS still work with a
		# roughly right RTC, so give up after a minute and say so
		started_wait = time.monotonic()
		notified = False
		synced = False
		while time.monotonic() - started_wait < 60:
			if not notified and time.monotonic() - started_wait > 5:
				notified = True
				warn('NTP sync taking longer than expected, still waiting...')

			time_val = SysCommand('timedatectl show --property=NTPSynchronized --value').decode()
			if time_val and time_val.strip() == 'yes':
				synced = True
				break
			time.sleep(1)

		if synced:
			info('NTP time synchronization completed')
		else:
			warn('NTP did not sync within 60 seconds, continuing anyway (or use --skip-ntp)')
	else:
		info('Skipping NTP time sync (may cause issues if system time is incorrect)')

	if not skip_wkd and SysInfo.arch() == 'x86_64':
		info('Waiting for Arch Linux keyring sync...')
		# same bound as NTP: a timer that never fires or a sync that never
		# returns (no route to the WKD host) must not hold the install
		deadline = time.monotonic() + 60
		timer = 'archlinux-keyring-wkd-sync.timer'
		service = 'archlinux-keyring-wkd-sync.service'
		# Wait for the timer to kick in
		while _service_started(timer) is None and time.monotonic() < deadline:
			time.sleep(1)

		# Wait for the service to enter a finished state
		keyring_state = _service_state(service)
		while keyring_state not in ('dead', 'failed', 'exited') and time.monotonic() < deadline:
			time.sleep(1)
			keyring_state = _service_state(service)

		if keyring_state == 'failed':
			warn('Arch Linux keyring sync failed')
		elif keyring_state not in ('dead', 'exited'):
			warn('Keyring sync did not finish within 60 seconds, continuing anyway (or use --skip-wkd)')
		else:
			info('Arch Linux keyring sync completed')
	else:
		info('Skipping keyring sync (--skip-wkd or non-x86_64 architecture)')


def _systemctl_target(installation: Installer, action: str, service: str) -> None:
	# host systemctl drives the target offline via --root=. A non-systemd
	# host (alpine, ...) has no systemctl binary, so run the target's own
	# systemctl inside the chroot instead. enable/disable only write unit
	# symlinks, so they work without a running pid1 in the chroot.
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
