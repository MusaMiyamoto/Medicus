"""Talk to medicus-authd."""

import json
import os
import socket

from . import SOCKET


class AuthError(Exception):
    pass


def call(cmd: str, **params) -> dict:
    path = os.getenv("MEDICUS_AUTH_SOCKET", SOCKET)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect(path)
            s.sendall(json.dumps({"cmd": cmd, **params}).encode() + b"\n")
            data = b""
            while not data.endswith(b"\n"):
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
    except OSError as e:
        raise AuthError("Får ikke kontakt med innloggingstjenesten.") from e
    reply = json.loads(data)
    if not reply.get("ok"):
        raise AuthError(reply.get("error", "Ukjent feil."))
    return reply
