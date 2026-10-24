import pytest

from tekst import dokument


def test_title_has_only_our_name():
    assert dokument.window_title(None, False) == "Uten tittel – Text"
    assert "Mousepad" not in dokument.window_title(None, True)


def test_title_marks_unsaved_changes(tmp_path):
    assert dokument.window_title(tmp_path / "vakt.txt", True) == "*vakt.txt – Text"


def test_reads_utf8_and_old_windows_files(tmp_path):
    (tmp_path / "a.txt").write_bytes("Blodtrykk ålreit".encode("utf-8"))
    (tmp_path / "b.txt").write_bytes("Blodtrykk ålreit".encode("cp1252"))
    assert dokument.read_text(tmp_path / "a.txt") == "Blodtrykk ålreit"
    assert dokument.read_text(tmp_path / "b.txt") == "Blodtrykk ålreit"


def test_refuses_binary_files(tmp_path):
    (tmp_path / "x.bin").write_bytes(b"\x7fELF\0\0\0")
    with pytest.raises(dokument.OpenError):
        dokument.read_text(tmp_path / "x.bin")


def test_save_replaces_the_whole_file(tmp_path):
    path = tmp_path / "notat.txt"
    path.write_text("gammel tekst som er lengre")
    dokument.write_text(path, "ny")
    assert path.read_text() == "ny"
    assert [p.name for p in tmp_path.iterdir()] == ["notat.txt"]
