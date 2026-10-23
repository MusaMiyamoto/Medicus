"""Virus scanning of attachments with ClamAV (clamd), over its local socket.

    scan(data) -> ("ren", None)            no virus found
                  ("virus", "Eicar-Test")  virus found: the file must be refused
                  ("ikke skannet", None)   scanner not running: the file is marked as unscanned

Uses clamd's INSTREAM command, so the file is never written to disk before it's checked.
"""

import os
import socket
import struct

SOCKET = os.getenv("MEDICUS_CLAMD_SOCKET", "/run/clamav/clamd.ctl")
CHUNK = 64 * 1024


def scan(data: bytes, path: str | None = None, timeout: float = 60) -> tuple[str, str | None]:
    path = path or SOCKET
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(path)
            s.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), CHUNK):
                piece = data[i:i + CHUNK]
                s.sendall(struct.pack("!L", len(piece)) + piece)
            s.sendall(struct.pack("!L", 0))
            reply = b""
            while not reply.endswith(b"\0"):
                chunk = s.recv(4096)
                if not chunk:
                    break
                reply += chunk
    except OSError:
        return "ikke skannet", None
    text = reply.rstrip(b"\0").decode(errors="replace")
    if text.endswith("FOUND"):
        return "virus", text.split(":", 1)[-1].rsplit(" ", 1)[0].strip()
    if text.endswith("OK"):
        return "ren", None
    return "ikke skannet", None
