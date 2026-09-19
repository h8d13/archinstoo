from typing import TYPE_CHECKING

from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.localization.catalog import locale_encoding, split_locale_name, uncomment_locale
from archinstoo.lib.output import debug, error, info, warn

if TYPE_CHECKING:
	from pathlib import Path

	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.locale import LocaleConfiguration

# writes the target's locale, console and graphical keyboard files; the
# listings and validation the menus use live in catalog.py


def set_locale(installation: Installer, locale_config: LocaleConfiguration) -> bool:
	# the menu keeps language and encoding apart; locale.gen names them
	# together, so the same splitting the encoding menu scopes itself by
	lang, _, modifier = split_locale_name(locale_config.sys_lang)
	encoding = locale_encoding(locale_config.sys_lang, locale_config.sys_enc)

	locale_gen = installation.target / 'etc/locale.gen'
	locale_gen_lines = locale_gen.read_text().splitlines(True)

	if not uncomment_locale(locale_gen_lines, locale_config.sys_lang, locale_config.sys_enc):
		error(f"Invalid locale: language '{locale_config.sys_lang}', encoding '{locale_config.sys_enc}'")
		return False
	# tools hardcoding LC_ALL=en_US.UTF-8 warn on every non-US system otherwise
	# https://github.com/archlinux/archinstall/issues/3764
	uncomment_locale(locale_gen_lines, 'en_US.UTF-8', 'UTF-8')
	locale_gen.write_text(''.join(locale_gen_lines))

	try:
		installation.arch_chroot('locale-gen')
	except SysCallError as e:
		error(f'Failed to run locale-gen on target: {e}')
		return False

	# always fully qualified: bare SUPPORTED entries ("en_IL UTF-8") compile
	# under the bare name, but localedef also registers a normalized-codeset
	# alias (locarchive.c), so LANG=en_IL.UTF-8 resolves and UTF-8 stays
	# visible to tools sniffing LANG (tmux et al.)
	(installation.target / 'etc/locale.conf').write_text(f'LANG={lang}.{encoding}{modifier}\n')
	info(f'Set locale LANG={lang}.{encoding}{modifier}')
	return True


def set_vconsole(installation: Installer, locale_config: LocaleConfiguration) -> None:
	kb_vconsole: str = locale_config.kb_layout
	font_vconsole: str = locale_config.console_font

	vconsole_dir: Path = installation.target / 'etc'
	vconsole_dir.mkdir(parents=True, exist_ok=True)
	vconsole_path: Path = vconsole_dir / 'vconsole.conf'

	vconsole_content = f'KEYMAP={kb_vconsole}\n'
	vconsole_content += f'FONT={font_vconsole}\n'

	vconsole_path.write_text(vconsole_content)
	info(f'Wrote to {vconsole_path} using {kb_vconsole} and {font_vconsole}')


def set_keyboard(installation: Installer, locale_config: LocaleConfiguration) -> bool:
	# Graphical (X11/Wayland) keyboard config, separate from the console
	# keymap in vconsole.conf. Writes the Xorg InputClass (00-keyboard.conf)
	# and the libxkbcommon env Wayland compositors read (XKB_DEFAULT_*).
	# No-op unless a layout is set, leaving graphical sessions at the
	# libxkbcommon 'us' default. Selections come pre-validated from the menu.
	layout = locale_config.xkb_layout
	if not layout.strip():
		debug('No graphical (XKB) keyboard layout set, skipping')
		return False

	variant = locale_config.xkb_variant

	# (Xorg InputClass option, vconsole.conf key, value). Layout is always
	# set, the rest only when chosen; the three consumers below all read
	# their own names off this one list
	settings = [('XkbLayout', 'XKBLAYOUT', layout)]
	optional = (
		('XkbModel', 'XKBMODEL', locale_config.xkb_model),
		('XkbVariant', 'XKBVARIANT', variant),
		('XkbOptions', 'XKBOPTIONS', locale_config.xkb_options),
	)
	settings += [(opt, key, val) for opt, key, val in optional if val]

	opt_lines = '\n'.join(f'    Option "{opt}" "{val}"' for opt, _, val in settings)
	content = f'Section "InputClass"\n    Identifier "system-keyboard"\n    MatchIsKeyboard "on"\n{opt_lines}\nEndSection\n'

	xorg_conf_dir = installation.target / 'etc/X11/xorg.conf.d'
	xorg_conf_dir.mkdir(parents=True, exist_ok=True)
	(xorg_conf_dir / '00-keyboard.conf').write_text(content)
	info(f'Wrote X11 keyboard config: layout={layout} variant={variant or "-"}')

	# systemd-localed reads the XKB layout from vconsole.conf in preference to
	# the Xorg InputClass (v253), and writes it back there, so that file is the
	# canonical store; 00-keyboard.conf above stays for X servers started
	# without localed in the picture
	_set_vconsole_xkb(installation, {key: val for _, key, val in settings})

	# Wayland: libxkbcommon reads neither file, so the layout has to reach the
	# session as env vars. Same names, XKBLAYOUT -> XKB_DEFAULT_LAYOUT
	installation.set_environment({f'XKB_DEFAULT_{key[3:]}': val for _, key, val in settings})

	return True


def _set_vconsole_xkb(installation: Installer, values: dict[str, str]) -> None:
	# set_vconsole() ran earlier in the install and owns KEYMAP/FONT; keep
	# those lines and replace the whole XKB* block, so a second call neither
	# stacks duplicates nor leaves a key the new selection dropped
	vconsole_path = installation.target / 'etc/vconsole.conf'
	lines = vconsole_path.read_text().splitlines() if vconsole_path.is_file() else []
	kept = [line for line in lines if not line.split('=')[0].strip().startswith('XKB')]

	vconsole_path.write_text('\n'.join(kept + [f'{k}={v}' for k, v in values.items()]) + '\n')
	debug(f'Wrote XKB keys to {vconsole_path}: {" ".join(values)}')


def set_timezone(installation: Installer, zone: str) -> bool:
	if not zone:
		debug('No timezone configured, leaving target default')
		return True

	# Validate against the target's tzdata, not the host's: the symlink
	# resolves inside the chroot, and a host may lack FHS zoneinfo (NixOS).
	if (installation.target / 'usr/share/zoneinfo' / zone).exists():
		(installation.target / 'etc' / 'localtime').unlink(missing_ok=True)
		installation.arch_chroot(['ln', '-s', f'/usr/share/zoneinfo/{zone}', '/etc/localtime'])
		info(f'Set timezone to {zone}')
		return True

	warn(f'Time zone {zone} does not exist, continuing with system default')

	return False
