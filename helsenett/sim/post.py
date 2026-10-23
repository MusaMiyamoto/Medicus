"""Medicus Post in the simulator: the message hub of the closed health network.

Inside the network every sender is verified (card login → HPR number), so messages carry the
sender's real identity. Email from outside arrives through a gateway that runs the phishing check,
blocks attachments and turns links into plain text.

The caller says who they are with the X-Medicus-HPR header (in the real network: a HelseID token).
"""

import json
import re
import secrets
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import bilder, virusscan
from .. import fnr as fnrlib
from ..phishing import check_email
from . import seed

MAX_FILES = 20


def now() -> str:
    return datetime.now().isoformat(timespec="minutes")


class ExternalIn(BaseModel):
    navn: str = Field(max_length=200)
    adresse: str = Field(max_length=320)
    svar_til: str = Field(default="", max_length=320)
    til: list[str] = Field(min_length=1)
    emne: str = Field(max_length=300)
    tekst: str = Field(max_length=50000)
    vedlegg_navn: list[str] = []


def make_router(store, files_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/api/post")
    lock = threading.Lock()
    files_dir.mkdir(parents=True, exist_ok=True)

    def save_file(data: bytes, name: str) -> dict:
        kind = bilder.kind_of(data)
        result, virus = virusscan.scan(data)
        if result == "virus":
            raise bilder.BildeFeil(f"Virus funnet ({virus}). Filen er stoppet.")
        file_id = secrets.token_hex(12)
        (files_dir / file_id).write_bytes(data)
        safe_name = re.sub(r"[^\w.\- ]", "_", Path(name).name)[:200] or "vedlegg"
        meta = {"id": file_id, "navn": safe_name, "type": kind, "bytes": len(data), "virusskanning": result}
        if kind == "dicom":
            meta["dicom"] = bilder.dicom_info(data)
        return meta

    def prepare(state: dict):
        """Attach synthetic images to seeded messages, and run the phishing check on external mail."""
        images = {
            "xray": (seed.OLA, "Ola Nordmann", "DX", "Røntgen thorax", "CHEST", "rontgen-thorax.dcm"),
            "mr": (seed.ERIK, "Erik Johansen", "MR", "MR caput", "HEAD", "mr-caput.dcm"),
        }
        for i, msg in enumerate(state["post"]):
            msg.setdefault("id", i + 1)
            if msg["vedlegg"] and isinstance(msg["vedlegg"][0], str):
                made = []
                for key in msg["vedlegg"]:
                    fnr, name, mod, desc, part, filename = images[key]
                    made.append(save_file(bilder.synthetic_dicom(name, fnr, mod, desc, part), filename))
                msg["vedlegg"] = made
            if msg["kanal"] == "ekstern" and "vurdering" not in msg:
                f = msg["fra"]
                msg["vurdering"] = check_email(f["navn"], f["adresse"], msg["emne"], msg["tekst"],
                                               msg["vedlegg_navn"], f.get("svar_til", "")).as_dict()

    with lock:
        if "post" not in store.data:
            store.data.update({"adresser": seed.addresses(), "post": seed.mail()})
        prepare(store.data)
        store.save()

    def me(hpr: str | None) -> str:
        if not hpr or f"hpr:{hpr}" not in {a["id"] for a in store.data["adresser"]}:
            raise HTTPException(401, "Ukjent avsender i helsenettet.")
        return f"hpr:{hpr}"

    def visible(msg: dict, address: str) -> bool:
        sender = msg["fra"].get("hpr")
        return address in msg["til"] or (sender and f"hpr:{sender}" == address)

    def summary(msg: dict, address: str) -> dict:
        level = "verifisert" if msg["kanal"] == "helsenett" else msg["vurdering"]["nivå"]
        return {"id": msg["id"], "tid": msg["tid"], "kanal": msg["kanal"], "fra": msg["fra"], "emne": msg["emne"],
                "nivå": level, "vedlegg": len(msg["vedlegg"]) + len(msg.get("vedlegg_navn", [])),
                "lest": address in msg["lest_av"], "rapportert": msg.get("rapportert", False)}

    def find(message_id: int, address: str) -> dict:
        msg = next((m for m in store.data["post"] if m["id"] == message_id), None)
        if msg is None or not visible(msg, address):
            raise HTTPException(404, "Fant ikke meldingen.")
        return msg

    @router.get("/adresser")
    def directory():
        return store.data["adresser"]

    @router.get("/innboks")
    def inbox(x_medicus_hpr: str = Header(None)):
        address = me(x_medicus_hpr)
        mine = [m for m in store.data["post"] if address in m["til"]]
        return [summary(m, address) for m in sorted(mine, key=lambda m: m["tid"], reverse=True)]

    @router.get("/sendt")
    def sent(x_medicus_hpr: str = Header(None)):
        address = me(x_medicus_hpr)
        mine = [m for m in store.data["post"] if m["fra"].get("hpr") and f"hpr:{m['fra']['hpr']}" == address]
        return [summary(m, address) for m in sorted(mine, key=lambda m: m["tid"], reverse=True)]

    @router.get("/{message_id}")
    def read(message_id: int, x_medicus_hpr: str = Header(None)):
        address = me(x_medicus_hpr)
        with lock:
            msg = find(message_id, address)
            if address not in msg["lest_av"]:
                msg["lest_av"].append(address)
                store.save()
        names = {a["id"]: a["navn"] for a in store.data["adresser"]}
        return {**msg, "til_navn": [names.get(t, t) for t in msg["til"]],
                "nivå": "verifisert" if msg["kanal"] == "helsenett" else msg["vurdering"]["nivå"]}

    @router.post("")
    def send(aktor: str = Form(...), til: list[str] = Form(...), emne: str = Form(..., max_length=300),
             tekst: str = Form(..., max_length=50000), fnr: str = Form(""),
             filer: list[UploadFile] = File(default=[])):
        sender = json.loads(aktor)
        address = me(sender.get("hpr"))
        known = {a["id"] for a in store.data["adresser"]}
        if not til or not set(til) <= known:
            raise HTTPException(422, "Velg mottakere fra adresseregisteret.")
        if fnr and (not fnrlib.is_valid(fnr) or fnr not in store.data["pasienter"]):
            raise HTTPException(422, "Ukjent pasient.")
        if len(filer) > MAX_FILES:
            raise HTTPException(422, f"Maks {MAX_FILES} vedlegg.")
        attachments = []
        for upload in filer:
            data = upload.file.read(bilder.MAX_BYTES + 1)
            if len(data) > bilder.MAX_BYTES:
                raise HTTPException(413, f"«{upload.filename}» er større enn 50 MB.")
            try:
                attachments.append(save_file(data, upload.filename or "vedlegg"))
            except bilder.BildeFeil as e:
                raise HTTPException(422, f"«{upload.filename}»: {e}") from e
        with lock:
            msg = {"id": max((m["id"] for m in store.data["post"]), default=0) + 1, "tid": now(),
                   "kanal": "helsenett", "fra": {k: sender[k] for k in ("navn", "rolle", "virksomhet", "hpr")},
                   "til": til, "emne": emne, "tekst": tekst, "fnr": fnr, "vedlegg": attachments, "lest_av": [address]}
            store.data["post"].append(msg)
            if fnr:
                names = {a["id"]: a["navn"] for a in store.data["adresser"]}
                what = "Melding" + (f" med {len(attachments)} vedlegg" if attachments else "")
                store.data["pasienter"][fnr]["innsyn"].append({
                    "tid": now(), "aktor": msg["fra"], "modus": "normal", "begrunnelse": "Samhandling om behandling",
                    "hva": f"{what} sendt til {', '.join(names[t] for t in til)}"})
            store.save()
        return {"id": msg["id"]}

    @router.post("/{message_id}/rapporter")
    def report(message_id: int, x_medicus_hpr: str = Header(None)):
        address = me(x_medicus_hpr)
        with lock:
            msg = find(message_id, address)
            msg["rapportert"] = True
            store.save()
        return {"ok": True}

    def attachment(file_id: str, address: str) -> dict:
        for msg in store.data["post"]:
            for meta in msg["vedlegg"]:
                if meta["id"] == file_id and visible(msg, address):
                    return meta
        raise HTTPException(404, "Fant ikke vedlegget.")

    @router.get("/vedlegg/{file_id}")
    def download(file_id: str, x_medicus_hpr: str = Header(None)):
        meta = attachment(file_id, me(x_medicus_hpr))
        return Response((files_dir / meta["id"]).read_bytes(), media_type=bilder.ALLOWED[meta["type"]],
                        headers={"Content-Disposition": f'attachment; filename="{meta["navn"]}"'})

    @router.get("/vedlegg/{file_id}/visning")
    def preview(file_id: str, x_medicus_hpr: str = Header(None)):
        meta = attachment(file_id, me(x_medicus_hpr))
        try:
            png = bilder.render_png((files_dir / meta["id"]).read_bytes())
        except bilder.BildeFeil as e:
            raise HTTPException(415, str(e)) from e
        return Response(png, media_type="image/png")

    @router.post("/ekstern")
    def receive_external(body: ExternalIn):
        """Simulates the e-mail gateway: an external email arrives and is checked."""
        with lock:
            msg = {"id": max((m["id"] for m in store.data["post"]), default=0) + 1, "tid": now(), "kanal": "ekstern",
                   "fra": {"navn": body.navn, "adresse": body.adresse, "svar_til": body.svar_til},
                   "til": body.til, "emne": body.emne, "tekst": body.tekst, "fnr": "",
                   "vedlegg_navn": body.vedlegg_navn, "vedlegg": [], "lest_av": [],
                   "vurdering": check_email(body.navn, body.adresse, body.emne, body.tekst,
                                            body.vedlegg_navn, body.svar_til).as_dict()}
            store.data["post"].append(msg)
            store.save()
        return {"id": msg["id"], "vurdering": msg["vurdering"]}

    return router
