from pathlib import Path

from archinstall.default_profiles.profile import GreeterType
from archinstall.lib.args import ArchConfig, ArchConfigHandler, Arguments
from archinstall.lib.hardware import GfxDriver
from archinstall.lib.models.application import (
	ApplicationConfiguration,
	Audio,
	AudioConfiguration,
	BluetoothConfiguration,
	PrintServiceConfiguration,
	ZramConfiguration,
)
from archinstall.lib.models.authentication import AuthenticationConfiguration, PrivilegeEscalation
from archinstall.lib.models.bootloader import Bootloader, BootloaderConfiguration
from archinstall.lib.models.device import DiskLayoutConfiguration, DiskLayoutType
from archinstall.lib.models.locale import LocaleConfiguration
from archinstall.lib.models.mirrors import CustomRepository, CustomServer, MirrorConfiguration, MirrorRegion, SignCheck, SignOption
from archinstall.lib.models.network import NetworkConfiguration, Nic, NicType
from archinstall.lib.models.packages import Repository
from archinstall.lib.models.profile import ProfileConfiguration
from archinstall.lib.models.users import Password, User
from archinstall.lib.profile.profiles_handler import profile_handler
from archinstall.lib.translationhandler import translation_handler
from pytest import MonkeyPatch


def test_default_args(monkeypatch: MonkeyPatch) -> None:
	monkeypatch.setattr('sys.argv', ['archinstall'])
	handler = ArchConfigHandler()
	args = handler.args
	assert args == Arguments(
		config=None,
		config_url=None,
		silent=False,
		dry_run=False,
		script=None,
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
			'archinstall',
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
			'--no-pkg-lookups',
			'--advanced',
			'--dry-run',
			'--silent',
		],
	)

	handler = ArchConfigHandler()
	args = handler.args

	assert args == Arguments(
		config=config_fixture,
		config_url='https://example.com',
		silent=True,
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
			'archinstall',
			'--config',
			str(config_fixture),
		],
	)

	handler = ArchConfigHandler()
	arch_config = handler.config

	# TODO: Use the real values from the test fixture instead of clearing out the entries
	arch_config.disk_config.device_modifications = []  # type: ignore[union-attr]

	assert arch_config == ArchConfig(
		script='test_script',
		app_config=ApplicationConfiguration(
			bluetooth_config=BluetoothConfiguration(enabled=True),
			audio_config=AudioConfiguration(audio=Audio.PIPEWIRE),
			print_service_config=PrintServiceConfiguration(enabled=True),
		),
		auth_config=AuthenticationConfiguration(
			root_enc_password=Password(enc_password='password_hash'),
			users=[
				User(
					username='user_name',
					password=Password(enc_password='password_hash'),
					sudo=True,
					groups=['wheel'],
				),
			],
			privilege_escalation=PrivilegeEscalation.Doas,
		),
		locale_config=LocaleConfiguration(
			kb_layout='us',
			sys_lang='en_US',
			sys_enc='UTF-8',
		),
		archinstall_language=translation_handler.get_language_by_abbr('en'),
		disk_config=DiskLayoutConfiguration(
			config_type=DiskLayoutType.Default,
			device_modifications=[],
			lvm_config=None,
			mountpoint=None,
		),
		profile_config=ProfileConfiguration(
			profile=profile_handler.parse_profile_config(
				{
					'custom_settings': {
						'Hyprland': {
							'seat_access': 'polkit',
						},
						'Sway': {
							'seat_access': 'seatd',
						},
					},
					'details': [
						'Sway',
						'Hyprland',
					],
					'main': 'Desktop',
				}
			),
			gfx_driver=GfxDriver.AllOpenSource,
			greeter=GreeterType.Lightdm,
		),
		mirror_config=MirrorConfiguration(
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
		parallel_downloads=66,
		swap=ZramConfiguration(enabled=False),
		timezone='UTC',
		services=['service_1', 'service_2'],
		custom_commands=["echo 'Hello, World!'"],
	)
