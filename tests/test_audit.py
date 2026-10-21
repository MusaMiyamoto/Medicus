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
