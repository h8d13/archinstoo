import ctypes
from ctypes.util import find_library

import pytest

from archinstoo.lib.authentication.crypt import (
	ROUNDS_INSTALL,
	hash_password,
	sha512_crypt,
)
from archinstoo.lib.models.users import Password

# vectors from Drepper's spec, https://www.akkadia.org/drepper/SHA-crypt.txt
SPEC_VECTORS = [
	(
		'Hello world!',
		'saltstring',
		5000,
		'$6$saltstring$svn8UoSVapNtMuq1ukKS4tPQd8iKwSMHWjl/O817G3uBnIFNjnQJuesI68u4OTLiBFdcbYEdFCoEOfaS35inz1',
	),
	(
		'Hello world!',
		'saltstringsaltstring',
		10000,
		'$6$rounds=10000$saltstringsaltst$OW1/O6BYHV6BcXZu8QVeXbDWra3Oeqh0sbHbbMCVNSnCM/UrjmM0Dp8vOuZeHBy/YTBmSK6H9qs/y3RnOaw5v.',
	),
	(
		(
			'a very much longer text to encrypt.  This one even '
			'stretches over morethan one line.'
		),
		'anotherlongsaltstring',
		1400,
		'$6$rounds=1400$anotherlongsalts$POfYwTEok97VWcjxIiSOjiykti.o/pQs.wPvMxQ6Fm7I6IoYN3CmLs66x9t0oSwbtEW7o7UmJEiDwGqd8p4ur1',
	),
	(
		'we have a short salt string but not a short password',
		'short',
		77777,
		'$6$rounds=77777$short$WuQyW2YR.hBNpjjRhpYD/ifIw05xdfeEyQoMxIXbkvr0gge1a1x3yRULJ5CCaUeOxFmtlcGZelFl5CxtgfiAc0',
	),
	(
		'a short string',
		'asaltof16chars..',
		123456,
		'$6$rounds=123456$asaltof16chars..$BtCwjqMJGx5hrJhZywWvt0RLE8uZ4oPwcelCjmw2kSYu.Ec6ycULevoBK25fs2xXgMNrCzIMVcgEJAstJeonj1',
	),
	# below the minimum, clamped to 1000
	(
		'the minimum number is still observed',
		'roundstoolow',
		10,
		'$6$rounds=1000$roundstoolow$kUMsbe306n21p9R.FRkW3IGn.S9NPN0x50YhH1xhLsPuWGsUSklZt58jaTfF4ZEQpyUNGc0dqbpBYYBaHHrsX.',
	),
]


@pytest.mark.parametrize(('password', 'salt', 'rounds', 'expected'), SPEC_VECTORS)
def test_spec_vectors(password: str, salt: str, rounds: int, expected: str) -> None:
	assert sha512_crypt(password.encode(), salt, rounds) == expected


def test_random_salt_shape() -> None:
	setting, salt, digest = sha512_crypt(b'hunter2').rsplit('$', 2)
	assert setting == '$6'
	assert len(salt) == 16
	assert len(digest) == 86


def test_matches_host_libc_crypt() -> None:
	# cross check against the system crypt() when the host has one (glibc/libxcrypt)
	name = find_library('crypt')
	if name is None:
		pytest.skip('no libcrypt on this host')
	lib = ctypes.CDLL(name)
	lib.crypt.restype = ctypes.c_char_p
	for n in (0, 1, 15, 16, 17, 63, 64, 65, 95, 96, 200):
		password = bytes(range(1, n + 1))
		assert lib.crypt(password, b'$6$abcdefgh').decode() == sha512_crypt(
			password, 'abcdefgh'
		)


def test_hash_password_uses_install_rounds() -> None:
	hashed = hash_password(Password(plaintext='hunter2'))
	assert hashed.startswith(f'$6$rounds={ROUNDS_INSTALL}$')


def test_hash_password_keeps_existing_hash() -> None:
	assert hash_password(Password(enc_password='$6$abc$def')) == '$6$abc$def'
