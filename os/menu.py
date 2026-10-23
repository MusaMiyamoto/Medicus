"""Medicus names and neutral icons for the programs users see, and which entries are hidden.

Run at build time:  python3 os/menu.py <output folder>
It writes .desktop files to <output>/usr/local/share/applications/. Files there take priority over
the packages' own files in /usr/share/applications, so the original programs stay untouched
(and keep getting updates) while the menu shows Medicus names and no other brands.
"""

import sys
from pathlib import Path

# file name: (new name, neutral icon, command)
# (Text is Medicus' own editor, usr/share/applications/medicus-tekst.desktop.)
RENAME = {
    "thunar.desktop": ("Files", "system-file-manager", "thunar %F"),
    "org.xfce.ristretto.desktop": ("Pictures", "medicus-bilder", "ristretto %U"),
    "org.gnome.Evince.desktop": ("Dokumenter", "x-office-document", "evince %U"),
    "xfce4-screenshooter.desktop": ("Skjermbilde", "camera-photo", "xfce4-screenshooter"),
    "org.pulseaudio.pavucontrol.desktop": ("Lyd", "audio-volume-high", "pavucontrol"),
    "xfce-mouse-settings.desktop": ("Mouse", "input-mouse", "xfce4-mouse-settings"),
    "xfce-backdrop-settings.desktop": ("Bakgrunnsbilde", "preferences-desktop-wallpaper", "xfdesktop-settings"),
    "xfce-display-settings.desktop": ("Skjerm", "video-display", "xfce4-display-settings"),
    "xfce-ui-settings.desktop": ("Utseende", "preferences-desktop-theme", "xfce4-appearance-settings"),
    "xfce4-accessibility-settings.desktop": ("Tilgjengelighet", "preferences-desktop-accessibility", "xfce4-accessibility-settings"),
    "xfce4-notifyd-config.desktop": ("Varsler", "preferences-system-notifications", "xfce4-notifyd-config"),
    "xfce4-power-manager-settings.desktop": ("Strøm", "battery", "xfce4-power-manager-settings"),
    "xfce4-screensaver-preferences.desktop": ("Skjermlås", "system-lock-screen", "xfce4-screensaver-preferences"),
    "xfce4-session-logout.desktop": ("Logg ut", "system-log-out", "xfce4-session-logout"),
}

# Hidden: other brands, things users shouldn't change, and anything that can run commands
# (terminals, the settings editor, keyboard shortcuts, the session and window-manager tools).
HIDE = [
    "debian-uxterm.desktop", "debian-xterm.desktop", "vim.desktop", "lynis.desktop",
    "xfce4-about.desktop", "xfce4-terminal-emulator.desktop", "xfce4-web-browser.desktop",
    "xfce4-mail-reader.desktop", "xfce4-file-manager.desktop", "xfce4-mime-settings.desktop",
    "xfce4-settings-editor.desktop", "xfce4-settings-manager.desktop", "xfce-settings-manager.desktop",
    "xfce-keyboard-settings.desktop", "xfce-session-settings.desktop", "xfce-wm-settings.desktop",
    "xfce-wmtweaks-settings.desktop", "xfce-workspaces-settings.desktop", "xfce4-color-settings.desktop",
    "panel-preferences.desktop", "panel-desktop-handler.desktop", "thunar-settings.desktop",
    "thunar-bulk-rename.desktop", "thunar-volman-settings.desktop", "org.xfce.mousepad-settings.desktop",
    "org.xfce.mousepad.desktop",
    "nm-connection-editor.desktop", "firefox-esr.desktop", "xfce4-appfinder.desktop",
]


# What the Start menu shows under the name.
COMMENTS = {
    "thunar.desktop": "Mapper og filer: dokumenter, bilder og nedlastinger",
    "org.xfce.ristretto.desktop": "Se bilder",
    "org.gnome.Evince.desktop": "Les PDF-dokumenter",
    "xfce4-screenshooter.desktop": "Ta bilde av skjermen",
    "org.pulseaudio.pavucontrol.desktop": "Lydstyrke for hodesett og høyttalere",
}


def desktop(name: str, icon: str, command: str, categories: str, comment: str = "") -> str:
    comment_line = f"Comment={comment}\n" if comment else ""
    return (f"[Desktop Entry]\nType=Application\nName={name}\n{comment_line}Icon={icon}\nExec={command}\n"
            f"Terminal=false\nCategories={categories}\n")


CATEGORIES = {
    "thunar.desktop": "Utility;FileManager;",
    "org.xfce.ristretto.desktop": "Graphics;Viewer;",
    "org.gnome.Evince.desktop": "Office;Viewer;",
    "xfce4-screenshooter.desktop": "Utility;",
    "org.pulseaudio.pavucontrol.desktop": "Settings;AudioVideo;",
    "xfce4-session-logout.desktop": "System;",
}


def main(out: str):
    folder = Path(out) / "usr/local/share/applications"
    folder.mkdir(parents=True, exist_ok=True)
    for file, (name, icon, command) in RENAME.items():
        categories = CATEGORIES.get(file, "Settings;DesktopSettings;")
        (folder / file).write_text(desktop(name, icon, command, categories, COMMENTS.get(file, "")),
                                   encoding="utf-8")
    for file in HIDE:
        (folder / file).write_text("[Desktop Entry]\nType=Application\nName=Skjult\nNoDisplay=true\nHidden=true\n",
                                   encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
