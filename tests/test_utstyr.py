"""Medical USB devices approved by IT (utstyr)."""

import pytest

import utstyr
from medicus import sikkerhet


def descriptors(*interfaces: tuple[int, int, int]) -> bytes:
    """Raw USB descriptors: device, configuration, then one interface descriptor per (class, sub, proto)."""
    device = bytes([18, 1]) + bytes(16)
    config = bytes([9, 2, 0, 0, len(interfaces), 1, 0, 0x80, 50])
    body = b"".join(bytes([9, 4, n, 0, 1, c, s, p, 0]) + bytes([7, 5, 0x81, 3, 8, 0, 10])  # + an endpoint
                    for n, (c, s, p) in enumerate(interfaces))
    return device + config + body


def plug(sysfs, port, vendor, product, name, serial, *interfaces, authorized="0"):
    folder = sysfs / port
    folder.mkdir(parents=True)
    for key, value in {"idVendor": vendor, "idProduct": product, "product": name, "serial": serial,
                       "authorized": authorized}.items():
        (folder / key).write_text(value + "\n")
    (folder / "descriptors").write_bytes(descriptors(*interfaces))


@pytest.fixture
def sysfs(tmp_path):
    root = tmp_path / "usb"
    plug(root, "1-1", "0911", "1f40", "SpeechMike", "SM123", (3, 0, 0), (1, 1, 0), (1, 2, 0), (255, 0, 0))  # ff: its own buttons
    plug(root, "1-2", "abcd", "0001", "Spirometer", "SP-9", (2, 2, 1), (10, 0, 0))   # shows up as a modem
    plug(root, "1-3", "1234", "5678", "Dermatoskop", "", (14, 1, 0), (8, 6, 80))     # camera + memory stick
    plug(root, "1-4", "046d", "c077", "Mus", "", (3, 1, 2), authorized="1")
    (root / "usb1").mkdir()          # a root hub
    (root / "1-1:1.0").mkdir()       # an interface folder
    return root


def test_interfaces_are_read_from_raw_descriptors(sysfs):
    devices = {d.port: d for d in utstyr.connected(sysfs)}
    assert set(devices) == {"1-1", "1-2", "1-3", "1-4"}
    assert devices["1-1"].interfaces == ["01:01:00", "01:02:00", "03:00:00", "ff:00:00"]
    assert devices["1-1"].serial == "SM123" and not devices["1-1"].authorized


def test_approve_one_unit_makes_a_strict_rule(sysfs):
    entries = []
    speechmike = utstyr.connected(sysfs)[0]
    entry = utstyr.approve(entries, speechmike, "Diktermikrofon, kontor 3", "eirik-strand", "2026-10-24")
    assert utstyr.rule(entry) == 'allow id 0911:1f40 serial "SM123" with-interface match-all { 01:01:00 01:02:00 03:00:00 ff:00:00 }'
    assert utstyr.status(speechmike, entries).startswith("godkjent")


def test_whole_model_has_no_serial(sysfs):
    entry = utstyr.approve([], utstyr.connected(sysfs)[0], "Diktermikrofoner", "it", "2026-10-24", whole_model=True)
    assert utstyr.rule(entry) == "allow id 0911:1f40 with-interface match-all { 01:01:00 01:02:00 03:00:00 ff:00:00 }"


@pytest.mark.parametrize("port, problem", [("1-2", "nettverk"), ("1-3", "lagring")])
def test_storage_and_network_can_never_be_approved(sysfs, port, problem):
    device = next(d for d in utstyr.connected(sysfs) if d.port == port)
    with pytest.raises(ValueError, match=problem):
        utstyr.approve([], device, "Utstyr", "it", "2026-10-24", whole_model=True)


def test_unit_approval_needs_a_serial_number(sysfs):
    device = utstyr.connected(sysfs)[0]
    device.serial = ""
    with pytest.raises(ValueError, match="serienummer"):
        utstyr.approve([], device, "Diktermikrofon", "it", "2026-10-24")


def test_vendor_rule_still_excludes_storage_network_and_wireless():
    entry = utstyr.approve_vendor([], "0911", "Alt fra diktatleverandøren", "it", "2026-10-24")
    assert utstyr.rule(entry) == "allow id 0911:* with-interface none-of { 02:*:* 08:*:* 0a:*:* e0:*:* }"
    with pytest.raises(ValueError):
        utstyr.approve_vendor([], "09;1", "Feil", "it", "2026-10-24")


def test_hand_edited_list_cannot_inject_rules(sysfs):
    entry = utstyr.approve([], utstyr.connected(sysfs)[0], "Mikrofon", "it", "2026-10-24")
    for bad in ({"serienummer": 'x" allow'}, {"grensesnitt": ["08:06:50"]}, {"produkt": "1f40 allow"}):
        with pytest.raises(ValueError):
            utstyr.rule({**entry, **bad})
    text = utstyr.rules_text([{**entry, "navn": "Mikrofon\nallow"}])
    assert "\nallow\n" not in text and text.count("allow id") == 1


def test_a_different_unit_or_changed_device_is_not_approved(sysfs):
    entries = []
    speechmike = utstyr.connected(sysfs)[0]
    utstyr.approve(entries, speechmike, "Mikrofon", "it", "2026-10-24")
    other = utstyr.Device("2-1", "0911", "1f40", serial="SM999", interfaces=speechmike.interfaces)
    changed = utstyr.Device("2-2", "0911", "1f40", serial="SM123", interfaces=[*speechmike.interfaces, "08:06:50"])
    assert utstyr.status(other, entries) == "blokkert"
    assert utstyr.status(changed, entries) == "blokkert"


def test_mouse_is_allowed_by_the_base_policy(sysfs):
    mouse = next(d for d in utstyr.connected(sysfs) if d.port == "1-4")
    assert utstyr.status(mouse, []).startswith("tillatt")


def test_save_remove_and_write_rules(tmp_path, sysfs):
    entries = []
    utstyr.approve(entries, utstyr.connected(sysfs)[0], "Mikrofon", "it", "2026-10-24")
    utstyr.approve_vendor(entries, "abcd", "Spirometre", "it", "2026-10-24")
    utstyr.save(entries, tmp_path / "liste.json")
    assert [e["nr"] for e in utstyr.load(tmp_path / "liste.json")] == [1, 2]
    utstyr.remove(entries, 1)
    rules = tmp_path / "rules.d" / "50-medisinsk-utstyr.conf"
    utstyr.write_rules(entries, rules)
    assert rules.stat().st_mode & 0o777 == 0o600
    assert "abcd:*" in rules.read_text() and "0911" not in rules.read_text()
    with pytest.raises(ValueError):
        utstyr.remove(entries, 7)


def test_security_center_shows_blocked_devices(sysfs):
    item = sikkerhet.medical_devices(utstyr.connected(sysfs), [])
    assert item["status"] == sikkerhet.INFO and "SpeechMike" in item["forklaring"] and "Mus" not in item["forklaring"]
