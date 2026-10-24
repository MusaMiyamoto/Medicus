"""Machine certificate in the TPM and approved WLANs (wlan)."""

from datetime import datetime, timedelta, timezone

import pytest

import wlan

PIN = "a1b2c3d4e5f60718"


def test_keyfile_uses_eap_tls_with_the_key_in_the_tpm():
    text = wlan.keyfile("Sykehus-Ansatt", "radius.sykehuset.no", "host/pc01.sykehuset.no", PIN, uid="u1")
    assert "key-mgmt=wpa-eap" in text and "eap=tls;" in text and "pmf=3" in text
    assert f"private-key={wlan.KEY_URI}" in text and "BEGIN" not in text  # never the key itself
    assert "domain-suffix-match=radius.sykehuset.no" in text  # won't talk to a fake access point
    assert f"ca-cert={wlan.CA}" in text and "ssid=Sykehus-Ansatt" in text


def test_wired_profile_uses_the_same_tpm_certificate():
    text = wlan.wired_keyfile("radius.sykehuset.no", "host/pc01.sykehuset.no", PIN, uid="u2")
    assert "type=ethernet" in text and "[ethernet]" in text and "eap=tls;" in text
    assert f"private-key={wlan.KEY_URI}" in text and "domain-suffix-match=radius.sykehuset.no" in text
    assert f"id={wlan.WIRED_NAME}" in text and wlan.WIRED_NAME.startswith("Medicus: ")  # tilgang.nett looks for this
    with pytest.raises(ValueError):
        wlan.wired_keyfile("radius.sykehuset.no\n[ipv4]", "host/pc01", PIN)


@pytest.mark.parametrize("ssid", ["", "x" * 33, "Gjest\nallow", "a;b"])
def test_bad_network_names_are_refused(ssid):
    with pytest.raises(ValueError):
        wlan.keyfile(ssid, "radius.sykehuset.no", "host/pc01", PIN)


@pytest.mark.parametrize("server", ["", "radius", "radius.sykehuset.no\nidentity=x", "*.no"])
def test_radius_server_must_be_a_name(server):
    with pytest.raises(ValueError):
        wlan.keyfile("Sykehus", server, "host/pc01", PIN)


def test_injection_through_identity_or_pin_is_refused():
    with pytest.raises(ValueError):
        wlan.keyfile("Sykehus", "radius.sykehuset.no", "host/pc01\n[802-1x]", PIN)
    with pytest.raises(ValueError):
        wlan.keyfile("Sykehus", "radius.sykehuset.no", "host/pc01", "pin\nx")


def test_connection_file_name_is_safe():
    assert wlan.connection_file("../../etc/passwd").name == "medicus-wlan-______etc_passwd.nmconnection"


def test_private_files_are_root_only(tmp_path):
    path = tmp_path / "x.nmconnection"
    wlan.write_private(path, "hemmelig")
    assert path.stat().st_mode & 0o777 == 0o600


def test_enddate_is_read():
    assert wlan.parse_enddate("notAfter=Oct 24 12:00:00 2027 GMT\n") == datetime(2027, 10, 24, 12, tzinfo=timezone.utc)


def test_security_center_line():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    assert wlan.certificate_status(False, None, 0, now)["status"] == "info"
    assert wlan.certificate_status(True, None, 0, now)["status"] == "info"
    assert wlan.certificate_status(True, now - timedelta(days=1), 1, now)["status"] == "feil"
    assert wlan.certificate_status(True, now + timedelta(days=10), 1, now)["status"] == "advarsel"
    assert wlan.certificate_status(True, now + timedelta(days=300), 2, now)["status"] == "ok"
