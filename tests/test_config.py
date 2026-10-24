from pathlib import Path

import pytest

from medicus.config import Settings


def test_defaults_without_environment():
    s = Settings.from_env({})
    assert s == Settings()
    assert s.llm_timeout == 300 and s.warmup is True and s.audit_log == Path("data/audit.jsonl")


def test_environment_overrides_with_the_right_types():
    s = Settings.from_env({
        "MEDICUS_PORT": "9000", "MEDICUS_LLM_TEMPERATURE": "0.1", "MEDICUS_WARMUP": "0",
        "MEDICUS_AUDIT_LOG": "/var/lib/medicus/audit.jsonl", "MEDICUS_WHISPER_COMPUTE": "float16",
        "OTHER": "ignored",
    })
    assert s.port == 9000 and s.llm_temperature == 0.1 and s.warmup is False
    assert s.audit_log == Path("/var/lib/medicus/audit.jsonl") and s.whisper_compute == "float16"


@pytest.mark.parametrize("value, expected", [("1", True), ("true", True), ("Ja", True), ("no", False), ("", False)])
def test_flags(value, expected):
    assert Settings.from_env({"MEDICUS_WARMUP": value}).warmup is expected


def test_a_bad_number_stops_the_service_at_start():
    # Better a clear error at start than a wrong limit in use all day.
    with pytest.raises(ValueError):
        Settings.from_env({"MEDICUS_LLM_TIMEOUT": "ten minutes"})
