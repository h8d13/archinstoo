# The temporary AUR build rules let grimoire's `pacman -S` for official repo
# deps keep the proxy env, and leave nothing behind once the build is done.

import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from archinstoo.lib.args import ArchConfig
from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.global_menu import GlobalMenu
from archinstoo.lib.models.authentication import (
	AuthenticationConfiguration,
	PrivilegeEscalation,
)
from archinstoo.lib.models.users import Password, User
from archinstoo.lib.pm import aur
from archinstoo.lib.tui import Tui

# as util-linux and pacman ship them
PAM_SU = (
	'#%PAM-1.0\n'
	'auth            sufficient      pam_rootok.so\n'
	'# Uncomment the following line to implicitly trust the "wheel" group.\n'
	'#auth           sufficient      pam_wheel.so trust use_uid\n'
	'auth            required        pam_unix.so\n'
	'account         required        pam_unix.so\n'
)
MAKEPKG_CONF = '#-- Command used to run pacman as root\n#PACMAN_AUTH=()\n'

# what the su rule shows the build, spelled out: this is the text that makes
# su passwordless for wheel
SU_PAM = 'auth sufficient pam_wheel.so trust use_uid\n' + PAM_SU
SU_MAKEPKG_CONF = (
	"#-- Command used to run pacman as root\nPACMAN_AUTH=(su root -c '%c')\n"
)


class _Target:
	# a target as create_users leaves it, and a mount(8) that only records:
	# what is mounted over a path is what the build would read there
	def __init__(
		self,
		root: Path,
		monkeypatch: pytest.MonkeyPatch,
		priv_esc: PrivilegeEscalation | None,
		with_password: bool = True,
	) -> None:
		self.root = root
		self.priv_esc = priv_esc
		self.with_password = with_password
		self.mounted: dict[str, str] = {}
		self.modes: dict[str, int] = {}
		self.copies: list[Path] = []
		self.during: dict[str, str] = {}
		self.builds: list[tuple[str, str | None]] = []
		self.strapped: list[str] = []
		self.warnings: list[str] = []
		self.failing: BaseException | None = None
		self.unmountable = False

		(root / 'usr/local/bin').mkdir(parents=True)
		self.pam = self._write('etc/pam.d/su', PAM_SU)
		self.makepkg_conf = self._write('etc/makepkg.conf', MAKEPKG_CONF)
		# sudo and doas are only set up for an elevated user with a password
		if with_password and priv_esc is PrivilegeEscalation.Sudo:
			(root / 'etc/sudoers.d').mkdir()
		if with_password and priv_esc is PrivilegeEscalation.Doas:
			self._write('etc/doas.conf', 'permit persist :wheel\n')

		monkeypatch.setattr(aur, 'run', self._run)
		monkeypatch.setattr(aur, 'warn', self.warnings.append)

	def _write(self, name: str, text: str) -> Path:
		path = self.root / name
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(text)
		return path

	def _run(self, cmd: list[str]) -> None:
		match cmd:
			case ['mount', '--bind', copy, over]:
				if self.unmountable:
					raise SysCallError(
						f'mount: {over}: permission denied', 32
					)
				name = str(Path(over).relative_to(self.root))
				self.mounted[name] = Path(copy).read_text()
				self.modes[name] = stat.S_IMODE(
					Path(copy).stat().st_mode
				)
				self.copies.append(Path(copy))
			case ['umount', over]:
				del self.mounted[str(Path(over).relative_to(self.root))]
			case _:
				raise AssertionError(cmd)

	def _arch_chroot(
		self, cmd: str, run_as: str | None = None, **_: object
	) -> None:
		# snapshot what grimoire would find while it runs
		self.builds.append((cmd, run_as))
		self.during = dict(self.mounted)
		for rule in ('etc/doas.conf', 'etc/sudoers.d/99-aur-build'):
			if (self.root / rule).exists():
				self.during[rule] = (self.root / rule).read_text()
		if self.failing:
			raise self.failing

	def build(self) -> None:
		installation = SimpleNamespace(
			target=self.root,
			add_additional_packages=self.strapped.extend,
			arch_chroot=self._arch_chroot,
		)
		password = (
			Password(enc_password='$y$hash') if self.with_password else None
		)
		auth = AuthenticationConfiguration(
			users=[User('ada', password, True)],
			privilege_escalation=self.priv_esc,
		)
		aur.run_grimoire_installation(['yay'], installation, auth)  # type: ignore[arg-type]

	def untouched(self) -> bool:
		# nothing mounted any more, no copy left, and the target's own files
		# never written
		return (
			not self.mounted
			and not any(copy.exists() for copy in self.copies)
			and self.pam.read_text() == PAM_SU
			and self.makepkg_conf.read_text() == MAKEPKG_CONF
		)


def test_sudo_rule_keeps_proxy_env(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	target = _Target(tmp_path, monkeypatch, PrivilegeEscalation.Sudo)
	target.build()

	rule = target.during['etc/sudoers.d/99-aur-build']
	assert 'Defaults:ada env_keep += "http_proxy https_proxy no_proxy' in rule
	assert 'ada ALL=(ALL) NOPASSWD: /usr/bin/pacman\n' in rule
	assert not (tmp_path / 'etc/sudoers.d/99-aur-build').exists()
	# su is left alone where sudo does the job
	assert not target.copies


def test_doas_rule_keeps_proxy_env(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	target = _Target(tmp_path, monkeypatch, PrivilegeEscalation.Doas)
	target.build()

	lines = target.during['etc/doas.conf'].splitlines()
	for cmd in ('pacman', '/usr/bin/pacman'):
		assert (
			'permit nopass setenv { http_proxy https_proxy '
			'no_proxy HTTP_PROXY HTTPS_PROXY NO_PROXY } ada as '
			f'root cmd {cmd}' in lines
		)
	# the user's own rules survive the cleanup, ours do not
	assert (tmp_path / 'etc/doas.conf').read_text() == 'permit persist :wheel\n'
	assert not target.copies


def test_su_rule_is_mounted_over_the_target_for_the_build_only(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	# no escalation tool: there is no sudoers.d to write a rule into, the
	# build once died on it
	target = _Target(tmp_path, monkeypatch, None)
	target.build()

	assert target.during == {
		'etc/pam.d/su': SU_PAM,
		# named for grimoire, which picks run0 first where polkit is installed
		'etc/makepkg.conf': SU_MAKEPKG_CONF,
	}
	# pam_wheel trusts the caller's own uid: the wheel member has to build
	(_, run_as), *_ = target.builds
	assert run_as == 'ada'
	# makepkg reads its conf as that user
	assert target.modes['etc/makepkg.conf'] == stat.S_IMODE(
		target.makepkg_conf.stat().st_mode
	)
	assert target.strapped
	assert target.untouched()
	assert not (tmp_path / 'etc/sudoers.d').exists()


def test_su_rule_takes_the_vendor_pam_file_where_etc_has_none(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	# Caeoma keeps /etc for machine state: PAM reads /usr/lib/pam.d there
	target = _Target(tmp_path, monkeypatch, None)
	target.pam.unlink()
	vendor = tmp_path / 'usr/lib/pam.d/su'
	vendor.parent.mkdir(parents=True)
	vendor.write_text(PAM_SU)
	target.build()

	assert target.during['usr/lib/pam.d/su'] == SU_PAM
	assert target.builds
	assert not target.mounted
	assert vendor.read_text() == PAM_SU
	assert not target.pam.exists()


@pytest.mark.parametrize('priv_esc', PrivilegeEscalation)
def test_passwordless_build_user_builds_through_su(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	priv_esc: PrivilegeEscalation,
) -> None:
	# create_users set nothing up for them, whatever the config names
	target = _Target(tmp_path, monkeypatch, priv_esc, with_password=False)
	target.build()

	assert target.during == {
		'etc/pam.d/su': SU_PAM,
		'etc/makepkg.conf': SU_MAKEPKG_CONF,
	}
	assert target.strapped
	assert target.untouched()


def test_run0_build_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	# it needs a booted system: nothing is built and no toolchain strapped
	target = _Target(tmp_path, monkeypatch, PrivilegeEscalation.Run0)
	target.build()

	assert not target.builds
	assert not target.strapped
	assert not target.copies
	assert target.warnings == [
		'AUR packages cannot build under run0, skipping them'
	]


def test_su_rule_is_taken_back_when_a_package_fails(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	target = _Target(tmp_path, monkeypatch, None)
	target.failing = SysCallError('makepkg failed', 1)
	target.build()

	assert target.during['etc/pam.d/su'] == SU_PAM
	assert target.untouched()


def test_su_rule_is_taken_back_when_the_build_is_interrupted(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	target = _Target(tmp_path, monkeypatch, None)
	target.failing = KeyboardInterrupt()
	with pytest.raises(KeyboardInterrupt):
		target.build()

	assert target.during['etc/pam.d/su'] == SU_PAM
	assert target.untouched()


def test_su_rule_leaves_a_makepkg_conf_with_its_own_tool_alone(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	# nothing to name su in: said, not silently skipped
	target = _Target(tmp_path, monkeypatch, None)
	target.makepkg_conf.write_text('PACMAN_AUTH=(doas)\n')
	target.build()

	assert target.during['etc/makepkg.conf'] == 'PACMAN_AUTH=(doas)\n'
	assert any('sets PACMAN_AUTH itself' in w for w in target.warnings)


@pytest.mark.parametrize('broken', ['no su PAM file', 'mount refused'])
def test_rule_that_cannot_be_set_up_does_not_stop_the_install(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch, broken: str
) -> None:
	# these packages are extras: master died here, before fstab was written
	target = _Target(tmp_path, monkeypatch, None)
	if broken == 'no su PAM file':
		target.pam.unlink()
	else:
		target.unmountable = True
	target.build()

	assert not target.builds
	assert not target.mounted
	assert any('AUR build rule failed' in w for w in target.warnings)


@pytest.mark.parametrize('with_password', [True, False])
@pytest.mark.parametrize('priv_esc', [None, *PrivilegeEscalation], ids=str)
def test_menu_refuses_aur_only_where_the_build_is_skipped(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
	priv_esc: PrivilegeEscalation | None,
	with_password: bool,
) -> None:
	target = _Target(tmp_path, monkeypatch, priv_esc, with_password)
	target.build()

	# the constructor registers its abort handler on the class
	monkeypatch.setattr(Tui, '_abort_handler', None)
	password = Password(enc_password='$y$hash') if with_password else None
	auth = AuthenticationConfiguration(
		root_enc_password=Password(enc_password='$y$hash'),
		users=[User('ada', password, True)],
		privilege_escalation=priv_esc,
	)
	menu = GlobalMenu(ArchConfig(auth_config=auth, aur_packages=['yay']))
	refused = any('AUR' in missing for missing in menu._missing_configs())

	assert refused == (not target.builds)
	# run0, and only once the user has the password it is set up with
	assert refused == (priv_esc is PrivilegeEscalation.Run0 and with_password)
