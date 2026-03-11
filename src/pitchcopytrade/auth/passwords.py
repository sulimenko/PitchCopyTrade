from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty")

    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    hash_b64 = base64.urlsafe_b64encode(derived).decode("ascii")
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt_b64}${hash_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, n_raw, r_raw, p_raw, salt_b64, expected_b64 = password_hash.split("$", 5)
    except ValueError:
        return False

    if algorithm != "scrypt":
        return False

    salt = _decode_b64(salt_b64)
    expected = _decode_b64(expected_b64)
    actual = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=int(n_raw),
        r=int(r_raw),
        p=int(p_raw),
        dklen=len(expected),
    )
    return hmac.compare_digest(actual, expected)


def _decode_b64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
