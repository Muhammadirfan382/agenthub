"""Password hashing and opaque session tokens.

Passwords use scrypt from the standard library: a memory-hard KDF, so no new
dependency is needed for a modern password hash. Session tokens are random
enough that a fast hash is the right choice for them — they are never guessed,
only stolen, and a stolen database should not yield usable tokens.
"""

import base64
import hashlib
import hmac
import secrets

# Tuned for an interactive login: roughly 100 ms and 32 MiB on a laptop.
DEFAULT_COST_EXPONENT = 15
MIN_PRODUCTION_COST_EXPONENT = 14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32

# Work factor for new hashes. Stored hashes carry their own parameters, so
# changing this never invalidates existing passwords. Only the test environment
# lowers it (see Settings.password_hash_cost_exponent), so that a suite which
# creates dozens of accounts does not spend all its time in the KDF.
_cost_exponent = DEFAULT_COST_EXPONENT


def configure_password_cost(exponent: int) -> None:
    global _cost_exponent
    _cost_exponent = exponent


SESSION_TOKEN_BYTES = 32
CSRF_TOKEN_BYTES = 32

# A hash of a value nobody can supply, used to keep the timing of a login
# attempt for an unknown address similar to one for a known address.
_DUMMY_PASSWORD = secrets.token_urlsafe(32)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=KEY_BYTES,
        # OpenSSL refuses to allocate more than maxmem; scrypt needs 128*N*r.
        maxmem=128 * n * r * 2,
    )


def hash_password(password: str) -> str:
    """Returns a self-describing hash: the parameters travel with the value."""
    n = 2**_cost_exponent
    salt = secrets.token_bytes(SALT_BYTES)
    key = _derive(password, salt, n, SCRYPT_R, SCRYPT_P)
    return f"scrypt$n={n},r={SCRYPT_R},p={SCRYPT_P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, encoded: str) -> bool:
    """False for a wrong password and for any malformed stored hash."""
    try:
        algorithm, parameters, salt_text, key_text = encoded.split("$")
        if algorithm != "scrypt":
            return False
        values = dict(item.split("=", 1) for item in parameters.split(","))
        n, r, p = int(values["n"]), int(values["r"]), int(values["p"])
        salt, expected = _unb64(salt_text), _unb64(key_text)
    except (ValueError, KeyError):
        return False

    return hmac.compare_digest(_derive(password, salt, n, r, p), expected)


def spend_dummy_hash() -> None:
    """Burns comparable time when the address is unknown, to limit enumeration."""
    verify_password(_DUMMY_PASSWORD, hash_password(_DUMMY_PASSWORD))


def new_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def hash_token(token: str) -> str:
    """Stores a fingerprint instead of the token itself."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(supplied: str, expected: str) -> bool:
    return hmac.compare_digest(supplied, expected)
