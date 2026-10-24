import os
import pwd

import pytest

from tilgang import rydd

ME = pwd.getpwuid(os.getuid())


@pytest.fixture
def machine(tmp_path):
    home_root, skel, temp = tmp_path / "home", tmp_path / "skel", tmp_path / "tmp"
    for folder in (home_root, skel / "Bilder", temp):
        folder.mkdir(parents=True)
    (skel / ".face").write_text("avatar")
    (skel / "Bilder" / "rontgen.dcm").write_text("syntetisk")
    home = home_root / ME.pw_name
    (home / "Nedlastinger").mkdir(parents=True)
    (home / "Nedlastinger" / "epikrise.pdf").write_text("pasientdata")
    (home / ".cache" / "nettleser").mkdir(parents=True)
    (home / ".cache" / "nettleser" / "historikk").write_text("besøkte sider")
    (home / ".face").write_text("endret")
    return home_root, skel, temp, home


def test_home_is_emptied_and_rebuilt_from_skel(machine):
    home_root, skel, _temp, home = machine
    removed = rydd.wipe_home(home, ME.pw_uid, ME.pw_gid, skel, home_root)
    assert removed == 3
    assert sorted(p.name for p in home.iterdir()) == [".face", "Bilder"]
    assert (home / ".face").read_text() == "avatar" and (home / "Bilder" / "rontgen.dcm").exists()
    assert oct(home.stat().st_mode & 0o777) == "0o700"


def test_symlinks_are_removed_never_followed(machine, tmp_path):
    home_root, skel, _temp, home = machine
    outside = tmp_path / "viktig"
    outside.mkdir()
    (outside / "fil").write_text("må ikke slettes")
    (home / "lenke").symlink_to(outside)
    rydd.wipe_home(home, ME.pw_uid, ME.pw_gid, skel, home_root)
    assert not (home / "lenke").exists() and (outside / "fil").read_text() == "må ikke slettes"


def test_only_folders_directly_under_home_are_wiped(machine, tmp_path):
    home_root, skel, _temp, home = machine
    for wrong in (tmp_path / "etc", home_root / ".." / "etc", home / "Nedlastinger"):
        with pytest.raises(ValueError):
            rydd.wipe_home(wrong, ME.pw_uid, ME.pw_gid, skel, home_root)
    (home_root / "lenket").symlink_to(tmp_path)
    with pytest.raises(ValueError):
        rydd.wipe_home(home_root / "lenket", ME.pw_uid, ME.pw_gid, skel, home_root)
    assert (tmp_path / "skel" / ".face").exists()


def test_missing_home_is_created(machine):
    home_root, skel, _temp, home = machine
    import shutil
    shutil.rmtree(home)
    rydd.wipe_home(home, ME.pw_uid, ME.pw_gid, skel, home_root)
    assert (home / ".face").exists()


def test_only_the_persons_own_temp_files_go(machine):
    _home_root, _skel, temp, _home = machine
    (temp / "mitt").write_text("x")
    (temp / "min-mappe" / "under").mkdir(parents=True)
    (temp / "andres").write_text("y")
    owner = lambda path: 99999 if path.name == "andres" else ME.pw_uid  # noqa: E731
    assert rydd.wipe_temp_files(ME.pw_uid, (temp, temp / "finnes-ikke"), owner) == 2
    assert [p.name for p in temp.iterdir()] == ["andres"]


def test_only_medicus_accounts_are_wiped_and_their_programs_stopped_first(machine):
    home_root, skel, temp, home = machine
    calls = []
    run = lambda cmd, **_: calls.append(cmd)  # noqa: E731
    assert not rydd.wipe_user(ME.pw_name, users=lambda: {"someone-else"}, run=run,
                              home_root=home_root, skel=skel, temp_dirs=(temp,))
    assert (home / "Nedlastinger").exists() and calls == []
    assert not rydd.wipe_user("finnes-ikke", users=lambda: {"finnes-ikke"}, run=run)
    assert rydd.wipe_user(ME.pw_name, users=lambda: {ME.pw_name}, run=run,
                          home_root=home_root, skel=skel, temp_dirs=(temp,))
    assert calls == [["/usr/bin/pkill", "-KILL", "-U", str(ME.pw_uid)]]
    assert not (home / "Nedlastinger").exists()


def test_it_staff_get_the_it_skeleton_back(machine, tmp_path):
    """The amber IT taskbar lives in /etc/skel-it; a wipe must not swap it for the normal one."""
    home_root, skel, temp, home = machine
    it_skel = tmp_path / "skel-it"
    it_skel.mkdir()
    (it_skel / ".face").write_text("IT")
    run = lambda cmd, **_: None  # noqa: E731
    me = lambda: {ME.pw_name}  # noqa: E731
    rydd.wipe_user(ME.pw_name, users=me, run=run, home_root=home_root, skel=skel, temp_dirs=(temp,),
                   it_users=me, it_skel=it_skel)
    assert (home / ".face").read_text() == "IT"
    rydd.wipe_user(ME.pw_name, users=me, run=run, home_root=home_root, skel=skel, temp_dirs=(temp,),
                   it_users=set, it_skel=it_skel)
    assert (home / ".face").read_text() == "avatar"
    # No IT skeleton on this machine (an older build): the normal one, never an empty home.
    rydd.wipe_user(ME.pw_name, users=me, run=run, home_root=home_root, skel=skel, temp_dirs=(temp,),
                   it_users=me, it_skel=tmp_path / "finnes-ikke")
    assert (home / ".face").read_text() == "avatar"


def test_pam_only_wipes_when_a_session_closes(monkeypatch):
    wiped = []
    monkeypatch.setattr(rydd, "wipe_user", lambda name: wiped.append(name))
    assert rydd.main([], {"PAM_TYPE": "open_session", "PAM_USER": "berg"}) == 0
    assert rydd.main([], {"PAM_USER": "berg"}) == 0
    assert wiped == []
    assert rydd.main([], {"PAM_TYPE": "close_session", "PAM_USER": "berg"}) == 0
    assert wiped == ["berg"]


def test_a_failed_wipe_never_stops_the_session_closing(monkeypatch):
    def broken(name):
        raise OSError("disk full")
    monkeypatch.setattr(rydd, "wipe_user", broken)
    assert rydd.main([], {"PAM_TYPE": "close_session", "PAM_USER": "berg"}) == 0


def test_boot_wipes_every_medicus_account_and_carries_on_after_an_error(monkeypatch):
    wiped = []

    def wipe(name):
        wiped.append(name)
        if name == "lie":
            raise OSError("feil")
    monkeypatch.setattr(rydd, "medicus_users", lambda: {"berg", "lie", "nodtilgang"})
    monkeypatch.setattr(rydd, "wipe_user", wipe)
    assert rydd.main(["--alle"]) == 0
    assert wiped == ["berg", "lie", "nodtilgang"]
