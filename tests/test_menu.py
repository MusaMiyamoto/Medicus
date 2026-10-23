import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("menu", Path(__file__).parent.parent / "os" / "menu.py")
menu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(menu)

BRANDS = ("firefox", "thunar", "mousepad", "ristretto", "xfce", "debian", "gnome", "mozilla", "evince")


def test_menu_names_carry_no_other_brands(tmp_path):
    menu.main(tmp_path)
    for f in (tmp_path / "usr/local/share/applications").glob("*.desktop"):
        text = f.read_text(encoding="utf-8")
        name = next(line for line in text.splitlines() if line.startswith("Name="))
        icon = next((line for line in text.splitlines() if line.startswith("Icon=")), "Icon=")
        assert not any(b in name.lower() for b in BRANDS), f"{f.name}: {name}"
        assert not any(b in icon.lower() for b in BRANDS), f"{f.name}: {icon}"


def test_the_names_the_user_asked_for(tmp_path):
    assert menu.RENAME["thunar.desktop"][0] == "Files"
    assert menu.RENAME["org.xfce.ristretto.desktop"][0] == "Pictures"
    assert menu.RENAME["xfce-mouse-settings.desktop"][0] == "Mouse"


def test_text_is_our_own_editor():
    desktop = Path(__file__).parent.parent / "os/config/includes.chroot/usr/share/applications/medicus-tekst.desktop"
    assert "Name=Text\n" in desktop.read_text(encoding="utf-8")
    assert "org.xfce.mousepad.desktop" in menu.HIDE


def test_terminals_and_command_tools_are_hidden():
    for f in ("debian-xterm.desktop", "debian-uxterm.desktop", "xfce4-settings-editor.desktop",
              "xfce-keyboard-settings.desktop", "xfce4-terminal-emulator.desktop"):
        assert f in menu.HIDE
