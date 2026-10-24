"""The SBOM written into every Medicus OS build (deploy/sbom.py)."""

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("sbom", Path(__file__).parent.parent / "deploy" / "sbom.py")
sbom = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sbom)

DEB = "openssl\t3.5.1-1\tamd64\nlibssl3t64\t3.5.1-1\tamd64\nbroken line\nfreerdp3-x11\t3.15.0+dfsg-2\tamd64\n"
PIP = json.dumps([{"name": "fastapi", "version": "0.115.0"}, {"name": "python_multipart", "version": "0.0.9"},
                  {"name": "", "version": "1"}])


def test_every_package_gets_a_purl_scanners_understand():
    bom = sbom.sbom(DEB, PIP, "e8e1a6c", now=datetime(2026, 10, 24, tzinfo=timezone.utc))
    purls = [c["purl"] for c in bom["components"]]
    assert "pkg:deb/debian/openssl@3.5.1-1?arch=amd64&distro=debian-13" in purls
    assert "pkg:deb/debian/freerdp3-x11@3.15.0%2Bdfsg-2?arch=amd64&distro=debian-13" in purls  # + is encoded
    assert "pkg:pypi/python-multipart@0.0.9" in purls  # PyPI names normalised
    assert len(purls) == 5 and purls == sorted(purls)  # broken and nameless lines are skipped
    assert {c["type"] for c in bom["components"] if c["name"].startswith("lib")} == {"library"}


def test_document_is_cyclonedx_1_5_and_names_the_build():
    bom = sbom.sbom(DEB, PIP, "e8e1a6c-dirty")
    assert (bom["bomFormat"], bom["specVersion"]) == ("CycloneDX", "1.5")
    assert bom["serialNumber"].startswith("urn:uuid:")
    assert bom["metadata"]["component"] == {"type": "operating-system", "name": "Medicus OS",
                                            "version": "e8e1a6c-dirty", "bom-ref": "medicus-os"}
    refs = [c["bom-ref"] for c in bom["components"]]
    assert len(refs) == len(set(refs))


def test_command_line(tmp_path, capsys):
    (tmp_path / "deb.tsv").write_text(DEB)
    (tmp_path / "pip.json").write_text(PIP)
    assert sbom.main([str(tmp_path / "deb.tsv"), str(tmp_path / "pip.json"), "v1"]) == 0
    assert json.loads(capsys.readouterr().out)["metadata"]["component"]["version"] == "v1"
    assert sbom.main([]) == 2


def test_python_packages_are_locked_with_hashes():
    """The OS build installs exact versions with hashes, so a changed package on PyPI stops the build."""
    root = Path(__file__).parent.parent
    lock = (root / "requirements.txt").read_text()
    pins = [line for line in lock.splitlines() if line and not line.startswith((" ", "#"))]
    assert pins and all("==" in p and p.endswith("\\") for p in pins)  # each pin is followed by its hashes
    assert lock.count("--hash=sha256:") >= len(pins)
    hook = (root / "os/config/hooks/normal/0100-medicus.hook.chroot").read_text()
    assert "--require-hashes -r /opt/medicus/requirements.txt" in hook
    assert "-r requirements.in" in (root / "requirements-dev.txt").read_text()
