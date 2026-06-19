import ctypes
import secrets
from ctypes.util import find_library
from pathlib import Path

from archinstoo.lib.output import debug


def _load_libcrypt() -> ctypes.CDLL:
	# Resolve via the linker (find_library / soname) rather than a fixed path,
	# so any host that exposes libcrypt on the dynamic-linker path just works:
	# find_library adapts to the distro specific soname
	for name in (find_library('crypt'), 'libcrypt.so', 'libcrypt.so.1', 'libcrypt.so.2'):
		if name:
			try:
				return ctypes.CDLL(name)
			except OSError:
				continue

	# musl (Alpine) folds crypt() into libc with no standalone libcrypt soname,
	# and without a toolchain find_library('crypt') returns None. CDLL(None) opens
	# the running process image, which has libc loaded and exposes crypt directly.
	try:
		lib = ctypes.CDLL(None)
	except OSError:
		lib = None

	# hasattr forces symbol resolution and swallows the AttributeError musl
	# raises when crypt is absent, so it doubles as the existence probe
	if lib is not None and hasattr(lib, 'crypt'):
		return lib

	raise OSError('libcrypt/libc crypt not found on the dynamic-linker path')


libcrypt = _load_libcrypt()

libcrypt.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
libcrypt.crypt.restype = ctypes.c_char_p

# crypt_gensalt is a libxcrypt symbol. glibc hosts have it; musl (Alpine) folds
# crypt() into libc but ships no gensalt, so accessing it raises. Detect once and
# fall back to a hand-built SHA-512 setting below when it is missing.
try:
	libcrypt.crypt_gensalt.argtypes = [ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p, ctypes.c_int]
	libcrypt.crypt_gensalt.restype = ctypes.c_char_p
	HAVE_GENSALT = True
except AttributeError:
	HAVE_GENSALT = False

# crypt(3) salt alphabet, used only for the musl SHA-512 fallback
_CRYPT_B64 = './0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

LOGIN_DEFS = Path('/etc/login.defs')


def _search_login_defs(key: str) -> str | None:
	# host may not ship /etc/login.defs (alpine without shadow); fall back to
	# the caller's default cost factor instead of crashing
	if not LOGIN_DEFS.is_file():
		return None

	defs = LOGIN_DEFS.read_text()
	for line in defs.split('\n'):
		line = line.strip()

		if line.startswith('#'):
			continue

		if line.startswith(key):
			return line.split(' ')[1]

	return None


def crypt_gen_salt(prefix: str | bytes, rounds: int) -> bytes:
	if isinstance(prefix, str):
		prefix = prefix.encode('utf-8')

	setting: bytes | None = libcrypt.crypt_gensalt(prefix, rounds, None, 0)

	if setting is None:
		raise ValueError(f'crypt_gensalt() returned NULL for prefix {prefix!r} and rounds {rounds}')

	return setting


def _sha512_salt() -> bytes:
	# SHA-512 crypt ($6$) is supported by both glibc and musl and accepted by
	# the target Arch; 16 random salt chars from the crypt(3) alphabet
	rand = ''.join(secrets.choice(_CRYPT_B64) for _ in range(16))
	return f'$6${rand}'.encode()


def _crypt_with(plaintext: bytes, salt: bytes, prefix: str) -> str | None:
	# crypt() signals "algorithm unsupported" in three ways: NULL, a sentinel
	# that does not start with the requested prefix (glibc "*0"/"*1"), or a
	# silent fallthrough to a 13-char DES hash. A result that doesn't begin with
	# the prefix we asked for means the hash isn't what we requested.
	result: bytes | None = libcrypt.crypt(plaintext, salt)
	if result is None:
		return None

	decoded = result.decode('utf-8')
	if not decoded.startswith(prefix):
		return None

	return decoded


def crypt_yescrypt(plaintext: str) -> str:
	# By default chpasswd in Arch uses PAM to hash the password with crypt_yescrypt
	# the PAM code https://github.com/linux-pam/linux-pam/blob/master/modules/pam_unix/support.c
	# shows that the hashing rounds are determined from YESCRYPT_COST_FACTOR in /etc/login.defs
	# If no value was specified (or commented out) a default of 5 is chosen
	if (value := _search_login_defs('YESCRYPT_COST_FACTOR')) is not None:
		rounds = int(value)
		if rounds < 3:
			rounds = 3
		elif rounds > 11:
			rounds = 11
	else:
		rounds = 5

	debug(f'Creating yescrypt hash with rounds {rounds}')

	enc_plaintext = plaintext.encode('utf-8')

	# try yescrypt when the host can build a $y$ salt; the result is validated so
	# a host that has crypt_gensalt but whose crypt() can't actually do yescrypt
	# (sentinel/DES) still falls through to SHA-512 rather than returning junk
	if HAVE_GENSALT:
		yescrypt = _crypt_with(enc_plaintext, crypt_gen_salt('$y$', rounds), '$y$')
		if yescrypt is not None:
			return yescrypt
		debug('crypt() did not honor yescrypt, falling back to SHA-512')
	else:
		# musl libc: no yescrypt and no crypt_gensalt at all
		debug('crypt_gensalt unavailable (musl), using SHA-512 crypt')

	sha512 = _crypt_with(enc_plaintext, _sha512_salt(), '$6$')
	if sha512 is None:
		raise ValueError('crypt() failed for both yescrypt and SHA-512')

	return sha512
