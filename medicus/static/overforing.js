// Transfer from Epic: load an export (file or straight from Epic), show it, then import on confirmation.
const $ = (id) => document.getElementById(id);
let preview = null;

function setStatus(message, isError = false) {
  $("status").textContent = message;
  $("status").classList.toggle("error", isError);
}

const birth = (iso) => (iso || "").split("-").reverse().join(".");
const items = (list, fmt) => list.length ? list.map((x) => `<li>${fmt(x)}</li>`).join("") : "<li class=\"muted\">Ingen</li>";
const joined = (...parts) => parts.filter(Boolean).map(esc).join(" – ");

function show(data) {
  preview = data;
  const p = data.pasient;
  $("who-is-it").innerHTML = `<div><strong>${esc(p.navn)}</strong>
    <span class="muted">født ${esc(birth(p.fodt))} · ${esc(p.fnr.slice(0, 6))} *****</span></div>
    <span class="tag">fra ${esc(data.kilde)}</span>`;
  const warnings = [...data.advarsler];
  if (!data.her) warnings.unshift(`Pasienten finnes ikke i ${data.journalsystem}. Registrer pasienten først.`);
  else if (data.her.navn !== p.navn) warnings.unshift(`Navnet i ${data.journalsystem} er «${data.her.navn}». Kontroller at det er samme person.`);
  $("warnings").innerHTML = warnings.length
    ? `<div class="banner warn"><ul>${warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>` : "";
  $("allergies").innerHTML = items(data.allergier, (a) => joined(a.stoff, a.reaksjon, a.alvorlighet && `alvorlighet ${a.alvorlighet.toLowerCase()}`));
  $("conditions").innerHTML = items(data.tilstander, (c) => joined(c.navn, c.status, c.siden && `fra ${birth(c.siden)}`));
  $("medicines").innerHTML = items(data.legemidler, (m) => joined(m.navn, m.dosering, m.status));
  $("documents").innerHTML = data.dokumenter.length ? data.dokumenter.map((d) => `<div class="transfer-doc">
      <strong>${esc(d.tittel)}</strong> <span class="muted">${esc(birth(d.dato))} ${d.forfatter ? "· " + esc(d.forfatter) : ""}</span>
      <pre>${esc(d.tekst)}</pre></div>`).join("") : '<p class="muted">Ingen tekstdokumenter.</p>';
  $("confirm-text").textContent = `Jeg har kontrollert at dette er ${p.navn}, født ${birth(p.fodt)}, og vil overføre opplysningene til ${data.journalsystem}.`;
  $("confirm").checked = false;
  $("confirm").disabled = !data.her;
  $("import").disabled = true;
  $("preview").hidden = false;
  $("preview").scrollIntoView({ behavior: "smooth" });
  setStatus("");
}

async function loadFile(file) {
  if (!file) return;
  const form = new FormData();
  form.append("fil", file);
  setStatus("Leser eksporten …");
  try {
    show(await api("/api/overforing/epic/fil", { method: "POST", body: form }));
  } catch (e) {
    setStatus(e.message, true);
  }
}

$("file").addEventListener("change", (e) => { loadFile(e.target.files[0]); e.target.value = ""; });
const drop = $("drop");
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); loadFile(e.dataTransfer.files[0]); });

$("fetch").addEventListener("click", async () => {
  setStatus("Henter fra Epic …");
  try {
    show(await api("/api/overforing/epic/hent", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fnr: $("fetch-fnr").value.trim() }) }));
  } catch (e) {
    setStatus(e.message, true);
  }
});

$("confirm").addEventListener("change", () => { $("import").disabled = !$("confirm").checked; });
$("cancel").addEventListener("click", () => { preview = null; $("preview").hidden = true; setStatus("Avbrutt. Ingenting ble overført."); });

$("import").addEventListener("click", async () => {
  $("import").disabled = true;
  try {
    const data = await api("/api/overforing/importer", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: preview.id, fnr: preview.pasient.fnr }) });
    $("preview").hidden = true;
    setStatus(`Ferdig: ${data.notater} notater er lagret i journalen til ${preview.pasient.navn} (${data.lagret_i}). ` +
      "Pasienten ser overføringen på Helsenorge.");
    preview = null;
  } catch (e) {
    $("import").disabled = false;
    setStatus(e.message, true);
  }
});
