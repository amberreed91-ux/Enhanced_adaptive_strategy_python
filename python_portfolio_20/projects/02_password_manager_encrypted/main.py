from __future__ import annotations

import base64
import hashlib
import hmac


def derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 200_000, dklen=32)


def xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right, strict=False))


def encrypt(secret: str, password: str, salt: bytes) -> str:
    key = derive_key(password, salt)
    payload = xor_bytes(secret.encode(), key)
    return base64.urlsafe_b64encode(payload).decode()


def decrypt(token: str, password: str, salt: bytes) -> str:
    key = derive_key(password, salt)
    payload = base64.urlsafe_b64decode(token.encode())
    return xor_bytes(payload, key).decode()


def run_demo() -> dict[str, object]:
    salt = b'portfolio-salt'
    token = encrypt('my-secret', 'correct-horse', salt)
    clear = decrypt(token, 'correct-horse', salt)
    ok = hmac.compare_digest(clear, 'my-secret')
    return {'project': 'password_manager_encrypted', 'round_trip_ok': ok}


if __name__ == '__main__':
    print(run_demo())
