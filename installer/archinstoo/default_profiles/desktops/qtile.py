from typing import TYPE_CHECKING, override

from archinstoo.default_profiles.desktops import provision_terminal_config
from archinstoo.default_profiles.xorg import XorgProfile
from archinstoo.lib.output import debug
from archinstoo.lib.profile.base import GreeterType, ProfileType

if TYPE_CHECKING:
	from archinstoo.lib.installer import Installer
	from archinstoo.lib.models.users import User


# qtile 0.37.0 shipped a session file whose Exec is a quoted
# `/bin/sh -c "..."`. Session wrappers take the whole command line as one
# argument and word-split it (`exec $@`, deliberate and documented in the SDDM
# script Arch's /etc/lightdm/Xsession comes from), and splitting is not
# parsing: the quotes stay literal, `sh -c '"systemctl'` dies on the stray
# quote after 0.2s, and the greeter returns, forever. Do not "fix" that line,
# quoting it would break every session that is a bare command. The wrapper
# sources an executable ~/.xsession first, so claim the session from there.
#
# qtile reverted that Exec upstream (9ffd76bb7) and dropped qtile.service with
# it, so the unit is 0.37.0-only: prefer it while it is there, since it brings
# up graphical-session.target and with it the portals, and fall back to the
# plain command the next release restores. WAYLAND_DISPLAY is left out of the
# import, this profile is Xorg and an unset variable only writes a line to
# .xsession-errors. The DESKTOP_SESSION guard keeps every other session the
# user might install on the normal path.
_QTILE_UNIT = '/usr/lib/systemd/user/qtile.service'

_XSESSION = f"""\
#!/bin/sh
if [ "$DESKTOP_SESSION" = qtile ]; then
	if [ -f {_QTILE_UNIT} ]; then
		systemctl --user import-environment DISPLAY XAUTHORITY XDG_SEAT \\
			XDG_VTNR XDG_SESSION_ID XDG_SESSION_TYPE XDG_SESSION_CLASS \\
			XDG_SESSION_DESKTOP XDG_CURRENT_DESKTOP DESKTOP_SESSION
		exec systemctl --user start --wait qtile.service
	fi

	exec qtile start
fi
"""


class QtileProfile(XorgProfile):
	needs_terminal = True

	def __init__(self) -> None:
		super().__init__('qtile', ProfileType.WindowMgr)

	@property
	@override
	def packages(self) -> list[str]:
		# the default config asks pango for "sans" and draws logo.png as the
		# wallpaper. gdk-pixbuf2 is a hard dep of qtile, a scalable font is
		# nothing's dep: without one the bar renders as boxes. dbus-fast is an
		# optdep qtile warns about on every start, resume signals need it
		return [
			'qtile',
			'ttf-liberation',
			'python-dbus-fast',
		]

	@override
	def provision(self, install_session: Installer, users: list[User]) -> None:
		# with no ~/.config/qtile/config.py qtile falls back to the same file
		# inside site-packages, which is root-owned and byte-compiled. writing
		# the doc copy gives the user the one they are meant to edit
		provision_terminal_config(
			install_session,
			users,
			install_session.target / 'usr/share/doc/qtile/default_config.py',
			'qtile/config.py',
			'guess_terminal()',
			template='guess_terminal("{terminal}")',
		)

		for user in users:
			xsession = install_session.target / 'home' / user.username / '.xsession'
			xsession.parent.mkdir(parents=True, exist_ok=True)
			xsession.write_text(_XSESSION)
			# the wrapper tests -x before sourcing; 0644 is the login loop
			xsession.chmod(0o755)
			debug(f'Wrote {xsession}')

			install_session.chown_tree(user.username, f'/home/{user.username}/.xsession')

	@property
	@override
	def default_greeter_type(self) -> GreeterType:
		return GreeterType.Lightdm
