"""Task Manager: reading processes, the protection rules, and the root helper that stops them."""

import ast
import sys
import re
import signal
from pathlib import Path

import pytest

from medicus.audit import AuditLog
from oppgaver import __main__ as helper
from oppgaver import prosesser, sprak, tjenester

ROOT = Path(__file__).parent.parent
OS = ROOT / "os/config"


def add(proc: Path, pid, comm, uid=1001, ppid=1, state="S", cpu=(10, 5), start=5000, rss=2560, cmdline=None):
    d = proc / str(pid)
    d.mkdir(parents=True)
    fields = [state, ppid] + [0] * 9 + list(cpu) + [0] * 6 + [start, 0, rss]
    (d / "stat").write_text(f"{pid} ({comm}) " + " ".join(str(f) for f in fields) + "\n")
    (d / "cmdline").write_bytes((cmdline or comm).replace(" ", "\0").encode() + b"\0")
    (d / "status").write_text(f"Name:\t{comm}\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n")
    return d


@pytest.fixture
def proc(tmp_path):
    p = tmp_path / "proc"
    p.mkdir()
    (p / "stat").write_text("cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 100 0 100 800 0 0 0 0 0 0\n")
    (p / "meminfo").write_text("MemTotal:  4000000 kB\nMemFree:  1000000 kB\nMemAvailable:  3000000 kB\n")
    add(p, 1, "systemd", uid=0, ppid=0)
    add(p, 2, "kthreadd", uid=0, ppid=0)
    add(p, 40, "kworker/0:1", uid=0, ppid=2)
    add(p, 300, "python3", uid=0, cmdline="python3 -I -c import sys; from tilgang.authd import main; main()")
    add(p, 900, "xfwm4", uid=1001)
    add(p, 1200, "python3", uid=1001, cmdline="python3 -I -c import sys; from nettleser.app import main")
    add(p, 1300, "python3", uid=1001, cmdline="python3 -m kalkulator")
    add(p, 1400, "my program (x)", uid=1002)
    return p


def test_reads_name_user_state_memory_and_start_time(proc):
    p = prosesser.read(1400, proc)
    assert p.comm == "my program (x)"  # brackets and spaces in the name
    assert p.uid == 1002 and p.state == "S" and p.status == "Venter"
    assert p.cpu_ticks == 15 and p.start == 5000 and p.rss == 2560 * prosesser.PAGE


def test_a_process_that_ended_is_none(proc):
    assert prosesser.read(4242, proc) is None


def test_medicus_programs_get_their_own_names(proc):
    assert prosesser.read(1200, proc).name == "Nettleser"
    assert prosesser.read(1300, proc).name == "Kalkulator"
    assert prosesser.read(300, proc).name == "Kortinnlogging"
    assert prosesser.read(900, proc).name == "xfwm4"


def test_a_word_in_a_file_name_is_not_a_medicus_program(tmp_path):
    add(tmp_path, 7, "mousepad", cmdline="mousepad /home/x/tekst-nettleser.txt")
    p = prosesser.read(7, tmp_path)
    assert p.name == "mousepad" and not p.holds_patient_work


def test_programs_that_can_hold_patient_work_are_marked(proc):
    assert prosesser.read(1200, proc).holds_patient_work
    assert not prosesser.read(1300, proc).holds_patient_work


@pytest.mark.parametrize("pid", [1, 2, 40, 300, 900])
def test_kernel_system_services_and_the_desktop_are_protected(proc, pid):
    assert prosesser.protected(prosesser.read(pid, proc), own_pid=99999)


@pytest.mark.parametrize("pid", [1200, 1300, 1400])
def test_user_programs_can_be_stopped(proc, pid):
    assert prosesser.protected(prosesser.read(pid, proc), own_pid=99999) is None


def test_the_task_manager_does_not_stop_itself(proc):
    assert prosesser.protected(prosesser.read(1300, proc), own_pid=1300)


def test_cpu_use_is_the_share_since_the_last_reading(proc):
    snap = prosesser.Snapshot(proc)
    snap.read()
    add(proc, 1500, "late")  # new since the first reading: no CPU figure yet
    (proc / "stat").write_text("cpu  200 0 200 1600 0 0 0 0 0 0\n")  # 1000 ticks later
    stat = proc / "1400/stat"
    stat.write_text(stat.read_text().replace(" 10 5 ", " 110 55 "))  # 150 more ticks
    found = {p.pid: p for p in snap.read()}
    assert found[1400].cpu == 15.0
    assert found[1300].cpu == 0.0 and found[1500].cpu == 0.0


def test_memory_used_and_total(proc):
    assert prosesser.memory(proc) == (1000000 * 1024, 4000000 * 1024)


# --- The root helper -------------------------------------------------------------------------------

class Killer:
    """Stands in for os.kill: records the signal and lets the process end (or not)."""

    def __init__(self, proc, ends=True):
        self.proc, self.ends, self.sent = proc, ends, []

    def __call__(self, pid, sig):
        self.sent.append((pid, sig))
        if self.ends:
            import shutil
            shutil.rmtree(self.proc / str(pid))


def entries(log: AuditLog):
    import json
    return [json.loads(line) for line in log.path.read_text().splitlines()]


def test_close_asks_the_program_to_end_and_logs_it(proc, tmp_path):
    log, kill = AuditLog(tmp_path / "a.jsonl"), Killer(proc)
    code = helper.stop(1200, 5000, False, proc=proc, kill=kill, audit=log, who="eirik", out=lambda *_: None)
    assert code == helper.OK and kill.sent == [(1200, signal.SIGTERM)]
    [e] = entries(log)
    assert e["action"] == "prosess_stoppet" and e["user"] == "eirik"
    assert e["details"] == {"pid": 1200, "program": "Nettleser", "bruker": str(e["details"]["bruker"]),
                            "tvungen": False}
    assert "cmdline" not in str(e) and "nettleser.app" not in str(e)  # never the command line
    assert log.verify()[0]


def test_force_close_sends_sigkill(proc, tmp_path):
    kill = Killer(proc)
    helper.stop(1400, 5000, True, proc=proc, kill=kill, audit=AuditLog(tmp_path / "a.jsonl"), who="eirik",
                out=lambda *_: None)
    assert kill.sent == [(1400, signal.SIGKILL)]


def test_protected_processes_are_refused_and_the_refusal_is_logged(proc, tmp_path):
    log, kill = AuditLog(tmp_path / "a.jsonl"), Killer(proc)
    for pid in (1, 300, 900):
        start = prosesser.read(pid, proc).start
        assert helper.stop(pid, start, True, proc=proc, kill=kill, audit=log, who="eirik",
                           out=lambda *_: None) == helper.PROTECTED
    assert kill.sent == []
    assert [e["action"] for e in entries(log)] == ["prosess_stopp_avvist"] * 3


def test_a_reused_pid_is_not_stopped(proc, tmp_path):
    kill = Killer(proc)
    code = helper.stop(1400, 4999, True, proc=proc, kill=kill, audit=AuditLog(tmp_path / "a.jsonl"),
                       who="eirik", out=lambda *_: None)
    assert code == helper.GONE and kill.sent == []


def test_a_program_that_does_not_answer_is_reported(proc, tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    code = helper.stop(1400, 5000, False, proc=proc, kill=Killer(proc, ends=False), audit=log, who="eirik",
                       wait=0.2, out=lambda *_: None)
    assert code == helper.STILL_RUNNING
    assert entries(log)[0]["action"] == "prosess_svarer_ikke"


def test_stopping_needs_root(monkeypatch, capsys):
    monkeypatch.setattr(helper.os, "geteuid", lambda: 1001)
    assert helper.main(["stopp", "1400", "5000"]) == helper.NOT_ROOT


# --- The window and the OS build -------------------------------------------------------------------

def test_every_text_has_english(monkeypatch):
    source = (ROOT / "oppgaver/app.py").read_text(encoding="utf-8")
    texts = {node.args[0].value for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_"
             and node.args and isinstance(node.args[0], ast.Constant)}
    shown = (set(prosesser.STATES.values()) | {t for _, t, _ in prosesser.PROGRAMS}
             | set(prosesser.PAGES.values()) | set(prosesser.OTHER_WORK.values()))
    reasons = re.findall(r'return "([^"]+)"', (ROOT / "oppgaver/prosesser.py").read_text(encoding="utf-8"))
    shown |= ({name for _, name, _ in tjenester.SERVICES} | {r for _, _, r in tjenester.SERVICES if r}
              | set(tjenester.STATES.values()) | {"Ukjent", tjenester.locked("sshd.service")})
    same_in_english = {"Program", "PID", "Status", "CPU"}
    missing = (texts | shown | set(reasons)) - set(sprak.EN) - same_in_english
    assert not missing, missing
    monkeypatch.setenv("LANG", "en_GB.UTF-8")
    assert sprak._("Tving avslutning") == "Force close"


def test_the_window_names_the_exit_codes(monkeypatch):
    from importlib import util
    if util.find_spec("gi") is None:
        pytest.skip("GTK not installed")
    app = pytest.importorskip("oppgaver.app")
    assert app.result_text(1, "X") == ("Feil PIN, eller IT-kortet er sperret.", True)
    assert app.result_text(0, "Nettleser") == ("Nettleser er avsluttet.", False)
    assert app.result_text(5, "X")[1] and app.result_text(3, "X")[1]


def test_the_os_uses_our_task_manager_only_in_it_mode():
    desktop = (OS / "includes.chroot/usr/share/medicus-it/applications/medicus-it-oppgaver.desktop").read_text()
    assert "Exec=medicus-oppgaver" in desktop and "xfce4-taskmanager" not in desktop
    packages = (OS / "package-lists/medicus.list.chroot").read_text().split()
    assert "xfce4-taskmanager" not in packages
    hook = (OS / "hooks/normal/0100-medicus.hook.chroot").read_text()
    assert re.search(r"for tool in [^;]*/usr/local/bin/medicus-oppgaver", hook)  # root:medicus-it 0750
    assert "/opt/medicus/oppgaver" in hook
    assert '"$REPO/oppgaver"' in (ROOT / "os/build.sh").read_text()
    assert not (OS / "includes.chroot/usr/share/applications/medicus-it-oppgaver.desktop").exists()


def test_the_stops_are_part_of_the_audit_checks():
    from medicus import revisjon
    assert Path("/var/lib/medicus-oppgaver/audit.jsonl") in revisjon.LOGS


GUI_CHECK = r"""
import sys
from gi.repository import Gio, GLib
from oppgaver import app, prosesser, tjenester

proc = prosesser.Process(pid=4242, ppid=1, comm="python3", cmdline="python3 -I -c from nettleser.app import main",
                         uid=1, user="annen", state="S", cpu_ticks=0, start=1, rss=0)

class Check(app.OppgaverApp):
    def __init__(self):
        super().__init__()
        self.set_flags(Gio.ApplicationFlags.NON_UNIQUE)  # never hand over to a Task Manager already open

    def do_activate(self):
        window = app.OppgaverWindow(self)
        window.present()
        window.pointer_on_list = True   # rows keep their order while the pointer is on the list
        window.fill()
        assert [(p.pid, p.start) for p in window.visible()] == window.order
        for force in (False, True):
            dialog = app.ConfirmWindow(window, proc, force, lambda *a: None)
            dialog.present()
            dialog.close()
        mine = app.OppgaverWindow(self, personal=True)
        mine.present()
        assert all(prosesser.user_may_close(p, __import__("os").getuid()) for p in mine.procs)
        for force in (False, True):
            dialog = app.ConfirmWindow(mine, proc, force, lambda *a: None, personal=True)
            dialog.present()
            assert dialog.pin.get_parent() is None  # no PIN for your own programs
            dialog.close()
        services = app.ServicesWindow(window, read=lambda: [
            tjenester.Service("medicus.service", "Pasientjournal (tjeneste)", "active", None),
            tjenester.Service("nftables.service", "Brannmur", "active", tjenester.SECURITY)])
        services.present()
        services.list.select_row(services.list.get_row_at_index(0))
        assert services.restart.get_sensitive()
        services.refresh()  # the 3-second update keeps the selection and the button
        assert services.restart.get_sensitive()
        services.list.select_row(services.list.get_row_at_index(1))
        assert not services.restart.get_sensitive()  # security services are locked
        services.close()
        print("ok")
        self.quit()

sys.exit(Check().run([]))
"""


def test_the_window_and_both_dialogs_open(tmp_path):
    """Builds the real window and the PIN dialogs on a virtual display (GTK's Broadway backend)."""
    import os
    import shutil
    import subprocess
    import time
    if not shutil.which("gtk4-broadwayd"):
        pytest.skip("gtk4-broadwayd not installed")
    display = ":17"
    env = {**os.environ, "GDK_BACKEND": "broadway", "BROADWAY_DISPLAY": display, "PYTHONPATH": str(ROOT),
           "XDG_RUNTIME_DIR": str(tmp_path)}  # the server's socket is here, so both need it
    server = subprocess.Popen(["gtk4-broadwayd", display], env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    try:
        time.sleep(1)
        run = subprocess.run([sys.executable, "-c", GUI_CHECK], env=env, capture_output=True, text=True, timeout=60)
    finally:
        server.terminate()
    assert run.returncode == 0 and "ok" in run.stdout, run.stderr[-2000:]


# --- Lukk program som henger: health personnel close their own work programs ------------------------

def personal(proc: Path):
    add(proc, 2001, "python3", uid=1001, cmdline="python3 -I -c from nettleser.app import main http://127.0.0.1:8000/pasient")
    add(proc, 2002, "python3", uid=1001, cmdline="python3 -I -c from nettleser.app import main http://127.0.0.1:8000/post")
    add(proc, 2003, "python3", uid=1001, cmdline="python3 -I -c from nettleser.app import main http://127.0.0.1:8000")
    add(proc, 2004, "python3", uid=1001, cmdline="python3 -I -c from nettleser.app import main https://www.nrk.no/")
    add(proc, 2005, "xfreerdp3", uid=1001,
        cmdline="xfreerdp3 /v:dips.ous.no:3389 /cert:deny /app:program:||dips,name:DIPS Arena +auto-reconnect")
    add(proc, 2006, "thunar", uid=1001)
    add(proc, 2007, "python3", uid=1001, cmdline="python3 -m tekst")
    add(proc, 2008, "xfce4-panel", uid=1001)
    add(proc, 2009, "nm-applet", uid=1001)
    add(proc, 2010, "python3", uid=1002, cmdline="python3 -m kalkulator")  # someone else's


def test_work_programs_have_the_names_from_the_start_menu(proc):
    personal(proc)
    names = {pid: prosesser.read(pid, proc).name for pid in range(2001, 2008)}
    assert names == {2001: "Pasientjournal", 2002: "Post", 2003: "Journalassistent", 2004: "Nettleser",
                     2005: "DIPS Arena", 2006: "Files", 2007: "Text"}
    assert prosesser.read(2005, proc).holds_patient_work  # the record system's window


def test_health_personnel_see_only_their_own_work_programs(proc):
    personal(proc)
    mine = {p.pid for p in prosesser.Snapshot(proc).read() if prosesser.user_may_close(p, 1001, own_pid=99999)}
    # Not the taskbar, the network icon, the desktop, system services or someone else's program.
    assert mine == {1200, 1300, 2001, 2002, 2003, 2004, 2005, 2006, 2007}


def test_closing_your_own_program_is_reported_for_the_audit_log(proc):
    personal(proc)
    told, kill = [], Killer(proc)
    code = helper.close_own(2001, 5000, False, proc=proc, kill=kill, uid=1001, tell=lambda *a: told.append(a))
    assert code == helper.OK and kill.sent == [(2001, signal.SIGTERM)]
    assert told == [("Pasientjournal", False, True)]  # name, forced, ended: never the command line


def test_force_close_and_a_program_that_still_hangs(proc):
    personal(proc)
    told = []
    code = helper.close_own(2005, 5000, True, proc=proc, kill=Killer(proc, ends=False), uid=1001,
                            tell=lambda *a: told.append(a), wait=0.2)
    assert code == helper.STILL_RUNNING and told == [("DIPS Arena", True, False)]


@pytest.mark.parametrize("pid", [2008, 2009, 2010, 300, 1])
def test_health_personnel_cannot_close_anything_else(proc, pid):
    personal(proc)
    kill = Killer(proc)
    start = prosesser.read(pid, proc).start
    assert helper.close_own(pid, start, True, proc=proc, kill=kill, uid=1001, tell=lambda *a: None) == helper.PROTECTED
    assert kill.sent == []


def test_a_reused_pid_is_not_closed(proc):
    personal(proc)
    kill = Killer(proc)
    assert helper.close_own(2001, 1, True, proc=proc, kill=kill, uid=1001, tell=lambda *a: None) == helper.GONE
    assert kill.sent == []


def test_the_report_never_blocks_closing(monkeypatch):
    def down(*_a, **_k):
        raise OSError("connection refused")
    monkeypatch.setattr(helper.urllib.request, "urlopen", down)
    helper.report("Post", False, True)  # no exception


def test_everyone_has_close_a_frozen_program_and_ctrl_shift_esc():
    entry = (OS / "includes.chroot/usr/share/applications/medicus-lukk-program.desktop").read_text(encoding="utf-8")
    assert "Exec=medicus-lukk-program" in entry and "Name[en]=Close a frozen program" in entry
    launcher = (OS / "includes.chroot/usr/local/bin/medicus-lukk-program").read_text()
    assert "main(personal=True)" in launcher and "-I" in launcher
    hook = (OS / "hooks/normal/0100-medicus.hook.chroot").read_text()
    assert "medicus-lukk-program" not in hook  # not locked to IT, unlike the full Task Manager
    keys = (OS / "includes.chroot/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/"
                 "xfce4-keyboard-shortcuts.xml").read_text()
    assert '"&lt;Primary&gt;&lt;Shift&gt;Escape" type="string" value="medicus-lukk-program"' in keys


# --- Tjenester: IT restarts a service that hangs ---------------------------------------------------

class Systemctl:
    def __init__(self, code=0):
        self.code, self.calls = code, []

    def __call__(self, cmd, **_kw):
        self.calls.append(cmd)
        return type("Done", (), {"returncode": self.code, "stdout": ""})()


def test_a_service_that_hangs_is_restarted_and_logged(tmp_path):
    log, run = AuditLog(tmp_path / "a.jsonl"), Systemctl()
    assert helper.restart("medicus.service", run=run, audit=log, who="eirik-strand", out=lambda *_: None) == helper.OK
    assert run.calls == [["systemctl", "restart", "medicus.service"]]
    (last,) = entries(log)
    assert last["user"] == "eirik-strand" and last["action"] == "tjeneste_omstartet"
    assert last["details"] == {"tjeneste": "medicus.service", "navn": "Pasientjournal (tjeneste)"}


@pytest.mark.parametrize("unit", ["medicus-auth.service", "medicus-oktvakt.service", "nftables.service",
                                  "apparmor.service", "usbguard.service", "auditd.service", "sshd.service",
                                  "lightdm.service", "--now", "medicus.service; reboot"])
def test_login_card_lock_security_and_unknown_services_are_refused(tmp_path, unit):
    log, run = AuditLog(tmp_path / "a.jsonl"), Systemctl()
    assert helper.restart(unit, run=run, audit=log, who="eirik-strand", out=lambda *_: None) == helper.PROTECTED
    assert run.calls == []
    assert entries(log)[-1]["action"] == "tjeneste_omstart_avvist"


def test_a_restart_that_fails_is_reported(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl")
    code = helper.restart("tinyproxy.service", run=Systemctl(code=1), audit=log, who="x", out=lambda *_: None)
    assert code == helper.FAILED and entries(log)[-1]["action"] == "tjeneste_omstart_feilet"


def test_restarting_needs_root(monkeypatch):
    monkeypatch.setattr(helper.os, "geteuid", lambda: 1001)
    assert helper.main(["omstart", "medicus.service"]) == helper.NOT_ROOT


def test_service_states_are_read_from_systemctl():
    out = ("Id=medicus.service\nActiveState=active\n\nActiveState=failed\nId=tinyproxy.service\n\n"
           "Id=nftables.service\nActiveState=active\n")
    run = lambda cmd, **kw: type("Done", (), {"stdout": out})()  # noqa: E731
    services = {s.unit: s for s in tjenester.read(run=run)}
    assert [s.unit for s in tjenester.read(run=run)] == [u for u, _, _ in tjenester.SERVICES]
    assert services["medicus.service"].status == "Kjører" and not services["medicus.service"].locked
    assert services["tinyproxy.service"].status == "Feilet"
    assert services["nftables.service"].locked == tjenester.SECURITY
    assert services["auditd.service"].status == "Ukjent"  # not in the output


def test_every_enabled_medicus_service_is_in_the_list():
    hook = (OS / "hooks/normal/0100-medicus.hook.chroot").read_text()
    enabled = set(re.findall(r"(medicus[\w-]*\.service)", " ".join(
        line for line in hook.splitlines() if line.startswith("systemctl enable"))))
    assert enabled <= set(tjenester.NAMES)
