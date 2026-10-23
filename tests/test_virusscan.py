import os
import socket
import struct
import tempfile
import threading

import pytest

from helsenett import virusscan


def fake_clamd(reply_for):
    """A tiny clamd stand-in on a UNIX socket that answers INSTREAM like the real one."""
    path = os.path.join(tempfile.mkdtemp(), "clamd.ctl")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(1)

    def run():
        conn, _ = server.accept()
        with conn:
            assert conn.recv(10) == b"zINSTREAM\0"
            data = b""
            while True:
                size = struct.unpack("!L", conn.recv(4, socket.MSG_WAITALL))[0]
                if size == 0:
                    break
                data += conn.recv(size, socket.MSG_WAITALL)
            conn.sendall(reply_for(data) + b"\0")
        server.close()

    threading.Thread(target=run, daemon=True).start()
    return path


EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def answer(data):
    return b"stream: Eicar-Signature FOUND" if b"EICAR" in data else b"stream: OK"


def test_clean_file():
    assert virusscan.scan(b"hello" * 50000, path=fake_clamd(answer)) == ("ren", None)


def test_virus_found():
    assert virusscan.scan(EICAR, path=fake_clamd(answer)) == ("virus", "Eicar-Signature")


def test_scanner_missing_is_reported_not_hidden(tmp_path):
    assert virusscan.scan(b"x", path=str(tmp_path / "none.ctl")) == ("ikke skannet", None)


def test_infected_upload_is_refused(tmp_path, monkeypatch):
    import json

    from fastapi.testclient import TestClient

    from helsenett.sim import seed
    from helsenett.sim.app import create_app

    sim = TestClient(create_app(tmp_path / "sim.json"))
    monkeypatch.setattr(virusscan, "SOCKET", fake_clamd(lambda _d: b"stream: Win.Test.EICAR_HDB-1 FOUND"))
    png = b"\x89PNG\r\n\x1a\n" + b"\0" * 64
    reply = sim.post("/api/post", data={"aktor": json.dumps(seed.BERG), "til": [f"hpr:{seed.LIE['hpr']}"],
                                        "emne": "x", "tekst": "x"}, files=[("filer", ("a.png", png, "image/png"))])
    assert reply.status_code == 422
    assert "Virus funnet" in reply.json()["detail"]
