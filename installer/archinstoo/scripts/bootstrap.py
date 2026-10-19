# Any-host bootstrap, following
# https://wiki.archlinux.org/title/Install_Arch_Linux_from_existing_Linux
# The Arch bootstrap tarball, unpacked as a chroot archinstoo then runs
# from: the host needs no pacman, keyring or arch-install-scripts.
#
# Runs on the host's python before any of archinstoo's deps exist, so it
# stays on stdlib-backed lib helpers (no pyparted). The host only needs:
#   python3 (>= 3.14) util-linux coreutils libarchive(bsdtar) udev gnupg
# gnupg is optional on x86_64 (checksum only without it, trusting TLS)
# libarchive's binary is libarchive-tools on Debian and Alpine, bsdtar on Fedora
# Alpine (mdev by default): apk add python3 util-linux coreutils
#   libarchive-tools gnupg eudev && setup-devd udev
#
# Usage: ./RUN --script bootstrap [-- archinstoo args...]
#   what follows -- runs inside the root, as given (no args: guided)
# BOOT_DIR    where the root lives, reused across runs (default /tmp/A2-boot;
#             override for persistent storage or non-tmpfs location)
# BOOT_MIRROR x86_64 mirror the tarball and packages come from

import argparse
import sys
from pathlib import Path

from archinstoo.lib.bootstrap import BootError, bootstrap
from archinstoo.lib.cli import script_help
from archinstoo.lib.exceptions import SysCallError
from archinstoo.lib.output import error


def main() -> int:
	parser = argparse.ArgumentParser(
		prog='python -m archinstoo --script bootstrap',
		description=script_help(Path(__file__)),
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	parser.add_argument(
		'inner',
		nargs='*',
		metavar='-- ARGS',
		help='archinstoo args, run inside the root',
	)
	args = parser.parse_args()
	try:
		return bootstrap(args.inner)
	except (BootError, SysCallError) as err:
		error(str(err))
		return 1
	except KeyboardInterrupt:
		return 130


sys.exit(main())
