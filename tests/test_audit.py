from medicus.audit import AuditLog


def test_new_log_verifies(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    assert log.verify() == (True, None)


def test_entries_chain_and_verify(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    first = log.record("anna", "transcribe", {"chars": 120})
    second = log.record("anna", "note_generated")
    assert second["prev"] == first["hash"]
    assert log.verify() == (True, None)


def test_edited_entry_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.record("anna", "transcribe")
    log.record("anna", "note_approved")
    log.record("anna", "note_approved")
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace("anna", "bjorn")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert log.verify() == (False, 2)


def test_deleted_entry_is_detected(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    for action in ("a", "b", "c"):
        log.record("anna", action)
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert log.verify() == (False, 2)


import json  # noqa: E402

import pytest  # noqa: E402

from medicus import audit as audit_mod  # noqa: E402


def anchor_of(log):
    data = json.loads(log.anchor_path.read_text())
    return bytes.fromhex(data["nokkel"]), data["fra_linje"]


def rebuild_chain(path, change):
    """What an attacker with full control of the machine does: edit, then recompute every hash."""
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    change(entries)
    prev, out = audit_mod.GENESIS, []
    for e in entries:
        e.pop("hash"), e.pop("mac", None)
        e["prev"] = prev
        e["hash"] = audit_mod._digest(e)
        e["mac"] = "0" * 64
        prev = e["hash"]
        out.append(json.dumps(e, ensure_ascii=False))
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def test_rebuilt_chain_passes_the_plain_check_but_not_the_anchor(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    for who in ("anna", "anna", "bjorn"):
        log.record(who, "patient_opened")
    anchor, start = anchor_of(log)
    assert log.verify(anchor, start) == (True, None)
    rebuild_chain(log.path, lambda entries: entries[1].update(user="carl"))
    assert log.verify() == (True, None)  # this is exactly the weakness of a plain hash chain
    assert log.verify(anchor, start) == (False, 1)  # every MAC is wrong without the old keys


def test_entries_cut_off_the_end_are_found_with_the_anchor(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    for action in ("a", "b", "c"):
        log.record("anna", action)
    anchor, start = anchor_of(log)
    lines = log.path.read_text(encoding="utf-8").splitlines()
    log.path.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")
    assert log.verify() == (True, None)
    assert log.verify(anchor, start) == (False, 3)


def test_the_key_on_the_machine_cannot_sign_the_past(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.record("anna", "a")
    log.record("anna", "b")
    stolen = bytes.fromhex(json.loads(log.key_path.read_text())["nokkel"])  # what an intruder finds now
    anchor, _ = anchor_of(log)
    first_entry = json.loads(log.path.read_text().splitlines()[0])
    assert audit_mod._mac(stolen, first_entry["hash"]) != first_entry["mac"]
    assert stolen == audit_mod.next_key(audit_mod.next_key(anchor))  # only forwards, never back
    assert oct(log.key_path.stat().st_mode & 0o777) == "0o600"


def test_anchor_is_left_for_it_to_take_away(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    assert not log.anchor_on_machine()
    log.record("anna", "a")
    assert log.anchor_on_machine()
    log.anchor_path.unlink()  # IT moved it
    log.record("anna", "b")
    assert not log.anchor_on_machine()  # no new anchor while the key series continues


def test_lost_key_file_never_stops_logging_and_starts_a_marked_new_series(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.record("anna", "a")
    log.anchor_path.unlink()
    log.key_path.unlink()  # an older Medicus, or deleted by someone
    log.record("anna", "login")
    lines = [json.loads(line) for line in log.path.read_text().splitlines()]
    assert [e["action"] for e in lines] == ["a", "audit_key_series_started", "login"]
    assert log.anchor_on_machine()  # the Sikkerhetssenter shows this
    anchor, start = anchor_of(log)
    assert start == 2 and log.verify(anchor, start) == (True, None)


def test_writing_reads_only_the_end_of_the_file(tmp_path, monkeypatch):
    log = AuditLog(tmp_path / "audit.jsonl")
    for i in range(300):
        log.record("anna", "x", {"i": i})
    monkeypatch.setattr(audit_mod, "TAIL_BYTES", 2048)
    log.record("anna", "last")
    assert log.verify(*anchor_of(log)) == (True, None)


@pytest.mark.parametrize("bad", ["{not json", ""])
def test_broken_key_file_starts_a_new_series_instead_of_failing(tmp_path, bad):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.record("anna", "a")
    log.key_path.write_text(bad)
    log.record("anna", "b")
    assert log.verify() == (True, None)


from medicus import revisjon  # noqa: E402


def two_logs(tmp_path):
    logs = (tmp_path / "auth" / "audit.jsonl", tmp_path / "app" / "audit.jsonl")
    for path in logs:
        AuditLog(path).record("anna", "login")
    return logs


def test_security_center_warns_while_an_anchor_is_on_the_machine(tmp_path):
    logs = two_logs(tmp_path)
    check = revisjon.status_check(logs)
    assert check["status"] == "advarsel" and "medicus-revisjon ankre" in check["forklaring"]
    for path in logs:
        path.with_name("audit.jsonl.anker").unlink()
    assert revisjon.status_check(logs)["status"] == "ok"
    assert revisjon.status_check((tmp_path / "finnes-ikke" / "audit.jsonl",))["status"] == "ok"


def test_it_moves_the_anchors_off_and_checks_the_logs_with_them(tmp_path):
    logs = two_logs(tmp_path)
    lines = []
    assert revisjon.main(["ankre"], logs, lines.append, ask=lambda _: "nei") == 1
    assert all(p.with_name("audit.jsonl.anker").exists() for p in logs)  # nothing deleted without a yes
    lines.clear()
    assert revisjon.main(["ankre"], logs, lines.append, ask=lambda _: "ja") == 0
    assert not any(p.with_name("audit.jsonl.anker").exists() for p in logs)
    vault = tmp_path / "hvelv.jsonl"
    vault.write_text("\n".join(line for line in lines if line.startswith("{")))
    out = []
    assert revisjon.main(["sjekk", str(vault)], logs, out.append) == 0
    assert all("i orden (med anker)" in line for line in out)
    rebuild_chain(logs[0], lambda entries: entries[0].update(user="carl"))
    out.clear()
    assert revisjon.main(["sjekk"], logs, out.append) == 0  # the chain alone is fooled
    assert revisjon.main(["sjekk", str(vault)], logs, out.append) == 1
    assert "ENDRET ved linje 1" in out[-2]
