import pytest


@pytest.fixture(autouse=True)
def norwegian(monkeypatch):
    """Medicus runs in Norwegian unless the session was started in English; tests do the same,
    whatever language the machine running them has. English tests set LANG themselves."""
    monkeypatch.setenv("LANG", "nb_NO.UTF-8")
