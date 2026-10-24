"""Wipe a person's home folder when their session ends, and every Medicus home folder at boot.

Medicus PCs are shared. Nothing one person did (downloads, browser history and cache, copied files)
may be left for the next person, least of all on the shared emergency account. Patient data belongs in
the record system, never in a home folder. Unsaved notes in the journal assistant are kept by the
Medicus service for 12 hours, not in the home folder, so they survive this.

Run by pam_exec when a desktop session closes (PAM_TYPE=close_session, PAM_USER=the person), which is
when someone logs out, a held session runs out, or another person logs in. Coming back with the same
card within the hold is not a close, so nothing is wiped then. At boot it runs with --alle, so a power
cut doesn't leave anything behind either.

Only Medicus accounts (the card groups and the emergency account) are touched, and only their own
folder directly under /home. Symlinks are removed, never followed.
"""

from __future__ import annotations

import grp
import os
import pwd
import shutil
import subprocess
import sys
import syslog
from pathlib import Path

from .sessionguard import medicus_users

HOME_ROOT = Path("/home")
SKEL = Path("/etc/skel")
# IT staff start from their own copy (amber taskbar, IT favourites), made at build time by it-panel.
IT_SKEL = Path("/etc/skel-it")
TEMP_DIRS = (Path("/tmp"), Path("/var/tmp"))


def it_staff() -> set[str]:
    try:
        return set(grp.getgrnam("medicus-it").gr_mem)
    except KeyError:
        return set()


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _chown_tree(root: Path, uid: int, gid: int) -> None:
    os.lchown(root, uid, gid)
    for folder, dirs, files in os.walk(root):
        for name in dirs + files:
            os.lchown(os.path.join(folder, name), uid, gid)


def wipe_home(home: Path, uid: int, gid: int, skel: Path = SKEL, home_root: Path = HOME_ROOT) -> int:
    """Empty the home folder and put back a fresh copy of the skeleton. Returns how many entries were removed."""
    if home.parent != home_root or home.is_symlink():
        raise ValueError(f"{home} er ikke en hjemmemappe direkte under {home_root}.")
    home.mkdir(mode=0o700, exist_ok=True)
    removed = 0
    for entry in list(home.iterdir()):
        _remove(entry)
        removed += 1
    shutil.copytree(skel, home, symlinks=True, dirs_exist_ok=True)
    _chown_tree(home, uid, gid)
    home.chmod(0o700)
    return removed


def wipe_temp_files(uid: int, dirs=TEMP_DIRS, owner=lambda path: path.lstat().st_uid) -> int:
    """The person's own files directly in the shared temp folders."""
    removed = 0
    for folder in dirs:
        try:
            entries = list(folder.iterdir())
        except FileNotFoundError:
            continue
        for entry in entries:
            try:
                if owner(entry) == uid:
                    _remove(entry)
                    removed += 1
            except FileNotFoundError:
                pass
    return removed


def wipe_user(name: str, users=medicus_users, run=subprocess.run, home_root: Path = HOME_ROOT,
              skel: Path = SKEL, temp_dirs=TEMP_DIRS, it_users=it_staff, it_skel: Path = IT_SKEL) -> bool:
    """Wipe one Medicus person. Anyone else (root, service accounts) is left alone."""
    if name not in users():
        return False
    try:
        account = pwd.getpwnam(name)
    except KeyError:
        return False
    if name in it_users() and it_skel.is_dir():
        skel = it_skel
    # Programs still running (a browser closing down) would write their files back.
    run(["/usr/bin/pkill", "-KILL", "-U", str(account.pw_uid)], check=False)
    removed = wipe_home(home_root / name, account.pw_uid, account.pw_gid, skel, home_root)
    removed += wipe_temp_files(account.pw_uid, temp_dirs)
    syslog.syslog(syslog.LOG_INFO, f"medicus-rydd: hjemmemappen til {name} er tømt ({removed} ting fjernet)")
    return True


def main(argv=None, environ=os.environ) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--alle"]:
        for name in sorted(medicus_users()):
            try:
                wipe_user(name)
            except (OSError, ValueError) as error:
                syslog.syslog(syslog.LOG_ERR, f"medicus-rydd: {name}: {error}")
        return 0
    if environ.get("PAM_TYPE") != "close_session":
        return 0
    try:
        wipe_user(environ.get("PAM_USER", ""))
    except (OSError, ValueError) as error:
        syslog.syslog(syslog.LOG_ERR, f"medicus-rydd: {error}")
    return 0  # a failed wipe is logged; it must never stop the session from closing


if __name__ == "__main__":
    sys.exit(main())
