"""Software bill of materials (SBOM) for a Medicus OS build, in CycloneDX 1.5 JSON.

Lists every Debian package and every Python package in the image with its exact version and a
package URL (purl), so a new vulnerability can be checked against a build in minutes, e.g. with
`grype sbom:medicus-os-amd64.sbom.cdx.json` or Dependency-Track. Runs inside the image at build time:

    dpkg-query -W -f '${Package}\\t${Version}\\t${Architecture}\\n' > deb.tsv
    /opt/medicus/.venv/bin/pip list --format=json > pip.json
    python3 sbom.py deb.tsv pip.json medicus-versjon > sbom.cdx.json
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

DISTRO = "debian-13"


def deb_components(tsv: str) -> list[dict]:
    components = []
    for line in tsv.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not parts[0] or not parts[1]:
            continue
        name, version, arch = parts
        purl = f"pkg:deb/debian/{quote(name)}@{quote(version, safe='')}?arch={arch}&distro={DISTRO}"
        components.append({"type": "library" if name.startswith("lib") else "application",
                           "name": name, "version": version, "purl": purl, "bom-ref": purl})
    return components


def pypi_components(pip_json: str) -> list[dict]:
    components = []
    for item in json.loads(pip_json or "[]"):
        name, version = item.get("name"), item.get("version")
        if not name or not version:
            continue
        # purl spec: PyPI names are lower-case with "-" for "_".
        purl = f"pkg:pypi/{quote(name.lower().replace('_', '-'))}@{quote(version, safe='')}"
        components.append({"type": "library", "name": name, "version": version, "purl": purl, "bom-ref": purl})
    return components


def sbom(deb_tsv: str, pip_json: str, medicus_version: str, now: datetime | None = None) -> dict:
    components = deb_components(deb_tsv) + pypi_components(pip_json)
    components.sort(key=lambda c: c["purl"])
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
            "component": {"type": "operating-system", "name": "Medicus OS", "version": medicus_version,
                          "bom-ref": "medicus-os"},
            "tools": {"components": [{"type": "application", "name": "medicus-sbom"}]},
        },
        "components": components,
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    deb_file, pip_file, version = argv
    with open(deb_file, encoding="utf-8") as deb, open(pip_file, encoding="utf-8") as pip:
        print(json.dumps(sbom(deb.read(), pip.read(), version), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
