from pathlib import Path

from pytest import MonkeyPatch

from archinstoo.default_profiles.profile import GreeterType
from archinstoo.lib.args import ArchConfig, ArchConfigHandler, Arguments
from archinstoo.lib.hardware import GfxDriver
from archinstoo.lib.models.application import (
	ApplicationConfiguration,
	Audio,
	AudioConfiguration,
	BluetoothConfiguration,
	Editor,
	EditorConfiguration,
	Firewall,
	FirewallConfiguration,
	Management,
	ManagementConfiguration,
	Monitor,
	MonitorConfiguration,
	PowerManagement,
	PowerManagementConfiguration,
	PrintServiceConfiguration,
	Security,
	SecurityConfiguration,
	ZramConfiguration,
)
from archinstoo.lib.models.authentication import AuthenticationConfiguration, PrivilegeEscalation
from archinstoo.lib.models.bootloader import Bootloader, BootloaderConfiguration
from archinstoo.lib.models.device import DiskLayoutConfiguration, DiskLayoutType
from archinstoo.lib.models.locale import LocaleConfiguration
from archinstoo.lib.models.mirrors import CustomRepository, CustomServer, MirrorRegion, PacmanConfiguration, SignCheck, SignOption
from archinstoo.lib.models.network import NetworkConfiguration, Nic, NicType
from archinstoo.lib.models.packages import Repository
from archinstoo.lib.models.users import Password, Shell, User
from archinstoo.lib.translationhandler import translation_handler


def test_default_args(monkeypatch: MonkeyPatch) -> None:
	monkeypatch.setattr('sys.argv', ['archinstoo'])
	handler = ArchConfigHandler()
	args = handler.args
	assert args == Arguments(
		config=None,
		config_url=None,
		dry_run=False,
		script='guided',
		mountpoint=Path('/mnt'),
		skip_ntp=False,
		skip_wkd=False,
		skip_boot=False,
		debug=False,
		offline=False,
		advanced=False,
	)


def test_correct_parsing_args(
	monkeypatch: MonkeyPatch,
	config_fixture: Path,
) -> None:
	monkeypatch.setattr(
		'sys.argv',
		[
			'archinstoo',
			'--config',
			str(config_fixture),
			'--config-url',
			'https://example.com',
			'--script',
			'execution_script',
			'--mountpoint',
			'/tmp',
			'--skip-ntp',
			'--skip-wkd',
			'--skip-boot',
			'--debug',
			'--offline',
			'--advanced',
			'--dry-run',
		],
	)

	handler = ArchConfigHandler()
	args = handler.args

	assert args == Arguments(
		config=config_fixture,
		config_url='https://example.com',
		dry_run=True,
		script='execution_script',
		mountpoint=Path('/tmp'),
		skip_ntp=True,
		skip_wkd=True,
		skip_boot=True,
		debug=True,
		offline=True,
		advanced=True,
	)


def test_config_file_parsing(
	monkeypatch: MonkeyPatch,
	config_fixture: Path,
) -> None:
	monkeypatch.setattr(
		'sys.argv',
		[
			'archinstoo',
			'--config',
			str(config_fixture),
		],
	)

	handler = ArchConfigHandler()
	arch_config = handler.config

	# TODO: Use the real values from the test fixture instead of clearing out the entries
	arch_config.disk_config.device_modifications = []  # type: ignore[union-attr]

	# Profile objects compare by identity, so check separately by name
	assert arch_config.profile_config is not None
	assert arch_config.profile_config.profiles
	assert arch_config.profile_config.profiles[0].name == 'Desktop'
	assert arch_config.profile_config.gfx_driver == GfxDriver.AllOpenSource
	assert arch_config.profile_config.greeter == GreeterType.Lightdm

	# Clear profile_config for main comparison
	arch_config.profile_config = None

	assert arch_config == ArchConfig(
		script='test_script',
		app_config=ApplicationConfiguration(
			bluetooth_config=BluetoothConfiguration(enabled=True),
			audio_config=AudioConfiguration(audio=Audio.PIPEWIRE),
			print_service_config=PrintServiceConfiguration(enabled=True),
			firewall_config=FirewallConfiguration(firewall=Firewall.UFW),
			management_config=ManagementConfiguration(tools=[Management.GIT, Management.MAN]),
			monitor_config=MonitorConfiguration(monitor=Monitor.HTOP),
			editor_config=EditorConfiguration(editor=Editor.VIM),
			power_management_config=PowerManagementConfiguration(power_management=PowerManagement.PPD),
			security_config=SecurityConfiguration(tools=[Security.APPARMOR, Security.FIREJAIL]),
		),
		auth_config=AuthenticationConfiguration(
			root_enc_password=Password(enc_password='password_hash'),
			users=[
				User(
					username='user_name',
					password=Password(enc_password='password_hash'),
					elev=True,
					groups=['wheel', 'adm', 'log'],
					shell=Shell.FISH,
				),
			],
			privilege_escalation=PrivilegeEscalation.Doas,
		),
		locale_config=LocaleConfiguration(
			kb_layout='us',
			sys_lang='en_US',
			sys_enc='UTF-8',
			console_font='ter-v16b',
		),
		archinstoo_language=translation_handler.get_language_by_abbr('en'),
		disk_config=DiskLayoutConfiguration(
			config_type=DiskLayoutType.Default,
			device_modifications=[],
			lvm_config=None,
			mountpoint=None,
		),
		profile_config=None,
		pacman_config=PacmanConfiguration(
			mirror_regions=[
				MirrorRegion(
					name='Australia',
					urls=['http://archlinux.mirror.digitalpacific.com.au/$repo/os/$arch'],
				),
			],
			custom_servers=[CustomServer('https://mymirror.com/$repo/os/$arch')],
			optional_repositories=[Repository.Testing],
			custom_repositories=[
				CustomRepository(
					name='myrepo',
					url='https://myrepo.com/$repo/os/$arch',
					sign_check=SignCheck.Required,
					sign_option=SignOption.TrustAll,
				),
			],
			parallel_downloads=66,
		),
		network_config=NetworkConfiguration(
			type=NicType.MANUAL,
			nics=[
				Nic(
					iface='eno1',
					ip='192.168.1.15/24',
					dhcp=True,
					gateway='192.168.1.1',
					dns=[
						'192.168.1.1',
						'9.9.9.9',
					],
				),
			],
		),
		bootloader_config=BootloaderConfiguration(
			bootloader=Bootloader.Systemd,
			uki=False,
			removable=False,
		),
		hostname='archy',
		kernels=['linux-zen'],
		ntp=True,
		packages=['firefox'],
		swap=ZramConfiguration(enabled=False),
		timezone='UTC',
		services=['service_1', 'service_2'],
		custom_commands=["echo 'Hello, World!'"],
	)
