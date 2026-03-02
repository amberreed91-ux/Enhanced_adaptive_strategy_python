from __future__ import annotations

import base64
import hashlib
import hmac
import json


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


def sign(header: dict[str, str], payload: dict[str, str], secret: str) -> str:
    head = b64url(json.dumps(header, separators=(',', ':')).encode())
    body = b64url(json.dumps(payload, separators=(',', ':')).encode())
    msg = f'{head}.{body}'.encode()
    sig = b64url(hmac.new(secret.encode(), msg, hashlib.sha256).digest())
    return f'{head}.{body}.{sig}'


def verify(token: str, secret: str) -> bool:
    head, body, sig = token.split('.')
    expected = sign(json.loads(base64.urlsafe_b64decode(head + '==')), json.loads(base64.urlsafe_b64decode(body + '==')), secret)
    return hmac.compare_digest(expected.split('.')[-1], sig)


def run_demo() -> dict[str, object]:
    token = sign({'alg': 'HS256', 'typ': 'JWT'}, {'sub': 'amber', 'role': 'admin'}, 'super-secret')
    return {'project': 'jwt_auth_service', 'verified': verify(token, 'super-secret')}


if __name__ == '__main__':
    print(run_demo())
