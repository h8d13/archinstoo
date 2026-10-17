import hashlib
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from archinstoo.lib.models.users import Password

# SHA-512 crypt ($6$), written from Ulrich Drepper's public domain
# spec: https://www.akkadia.org/drepper/SHA-crypt.txt
# Same output as glibc/libxcrypt/musl crypt(), need no libcrypt on hosts:
# `passwd` or `chpasswd` on the target rehashes using it regardless.

# crypt(3) base64 alphabet, not the RFC 4648 one
B64 = './0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

ROUNDS_DEFAULT = 5000
ROUNDS_MIN = 1000
ROUNDS_MAX = 999_999_999
SALT_MAX = 16

# well above the spec default of 5000 ~0.3s on a intel i5
# same figure passlib picked for sha512_crypt
ROUNDS_INSTALL = 656_000


def _repeat(digest: bytes, length: int) -> bytes:
	# digest repeated to fill exactly length bytes
	return (digest * (length // len(digest) + 1))[:length]


def _b64_from_24bit(b2: int, b1: int, b0: int, n: int) -> str:
	w = (b2 << 16) | (b1 << 8) | b0
	out = ''
	for _ in range(n):
		out += B64[w & 0x3F]
		w >>= 6
	return out


def _encode(dc: bytes) -> str:
	# spec step 22: 21 byte triples i, i+21, i+42 rotated by i % 3,
	# then the lone last byte as 2 chars
	out = ''
	for i in range(21):
		t = (dc[i], dc[i + 21], dc[i + 42])
		r = i % 3
		out += _b64_from_24bit(t[r], t[(r + 1) % 3], t[(r + 2) % 3], 4)
	return out + _b64_from_24bit(0, 0, dc[63], 2)


def gen_salt() -> str:
	return ''.join(secrets.choice(B64) for _ in range(SALT_MAX))


def sha512_crypt(password: bytes, salt: str | None = None, rounds: int = ROUNDS_DEFAULT) -> str:
	salt_b = (salt if salt is not None else gen_salt()).encode()[:SALT_MAX]
	# spec clamps out of range rounds instead of failing
	rounds = min(max(rounds, ROUNDS_MIN), ROUNDS_MAX)
	pw_len = len(password)

	# digest B, fed into digest A
	db = hashlib.sha512(password + salt_b + password).digest()

	# digest A: pw + salt, B stretched to pw length, then B or pw per bit of pw length
	ctx = hashlib.sha512(password + salt_b + _repeat(db, pw_len))
	i = pw_len
	while i:
		ctx.update(db if i & 1 else password)
		i >>= 1
	da = ctx.digest()

	# P and S sequences stand in for the password and salt in the rounds
	ctx = hashlib.sha512()
	for _ in range(pw_len):
		ctx.update(password)
	dp = _repeat(ctx.digest(), pw_len)
	ds = _repeat(hashlib.sha512(salt_b * (16 + da[0])).digest(), len(salt_b))

	dc = da
	for r in range(rounds):
		ctx = hashlib.sha512(dp if r & 1 else dc)
		if r % 3:
			ctx.update(ds)
		if r % 7:
			ctx.update(dp)
		ctx.update(dc if r & 1 else dp)
		dc = ctx.digest()

	# default rounds are implicit, anything else is spelled out in the setting
	setting = '$6$' if rounds == ROUNDS_DEFAULT else f'$6$rounds={rounds}$'
	return f'{setting}{salt_b.decode()}${_encode(dc)}'


def hash_password(password: Password) -> str:
	# a config already carries the hash, the menu only the plaintext
	return password.enc_password or sha512_crypt(password.plaintext.encode('utf-8'), rounds=ROUNDS_INSTALL)
