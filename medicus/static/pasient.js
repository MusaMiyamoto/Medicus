let fnr = null;
let reasonGiven = null;  // for a patient outside the clinician's list: reused when the record is reloaded
const statusEl = document.getElementById("status");

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function criticalHtml(k) {
  const parts = [];
  for (const a of k.allergier) {
    parts.push(`<div class="item"><span class="tag danger">Allergi</span> <b>${esc(a.stoff)}</b> – ${esc(a.reaksjon)} (${esc(a.alvorlighet.toLowerCase())})</div>`);
  }
  for (const t of k.tilstander) {
    parts.push(`<div class="item"><span class="tag danger">Tilstand</span> <b>${esc(t.navn)}</b><div>${esc(t.merknad)}</div></div>`);
  }
  for (const i of k.implantater) {
    parts.push(`<div class="item"><span class="tag">Implantat</span> <b>${esc(i.navn)}</b><div>${esc(i.merknad)}</div></div>`);
  }
  for (const p of k.parorende) {
    parts.push(`<div class="item"><span class="tag">Pårørende</span> ${esc(p.navn)} (${esc(p.relasjon.toLowerCase())}), tlf. ${esc(p.telefon)}</div>`);
  }
  return parts.join("") || "<p class='muted'>Ingen kritisk informasjon registrert.</p>";
}

function render(record) {
  const p = record.pasient;
  document.getElementById("name").textContent = `${p.navn} · født ${p.fodt}`;
  document.getElementById("critical").innerHTML = criticalHtml(record.kritisk);
  document.getElementById("prescriptions").innerHTML = record.resepter.map((r) => `
    <div class="item"><b>${esc(r.legemiddel)}</b> – ${esc(r.dosering)}
      <div class="muted">${esc(r.indikasjon)} · ${esc(r.aktor.navn)}, ${when(r.tid)}</div></div>`).join("")
    || "<p class='muted'>Ingen resepter.</p>";
  document.getElementById("encounters").innerHTML = record.kontakter.map((k) => `
    <div class="item"><b>${esc(k.type)}</b> – ${esc(k.virksomhet)}
      <div class="muted">${when(k.tid)} · ${esc(k.aktor.navn)} (${esc(k.aktor.rolle.toLowerCase())})</div>
      <pre>${esc(k.notat)}</pre></div>`).join("") || "<p class='muted'>Ingen besøk registrert.</p>";
}

function show(number, record, reason = null) {
  fnr = number;
  reasonGiven = reason;
  render(record);
  document.getElementById("search").hidden = true;
  document.getElementById("record").hidden = false;
  setStatus("Tilgangen er logget. Pasienten kan se den på Helsenorge.");
}

async function openRecord(number) {
  try {
    show(number, await api(`/api/pasient/${encodeURIComponent(number)}`));
  } catch (e) {
    if (e.status === 409 && e.detail && e.detail.begrunnelse_kreves) askReason(number, e.detail.valg);
    else setStatus(e.message, true);
  }
}

// --- Patients outside the clinician's own list: ask why --------------------
const reasonDialog = document.getElementById("why");
const reasonChoice = document.getElementById("why-choice");
const reasonText = document.getElementById("why-text");
const reasonError = document.getElementById("why-error");
let reasonFor = null;

function openWithReason(number, reason) {
  return api(`/api/pasient/${encodeURIComponent(number)}/apne`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(reason),
  });
}

function askReason(number, choices) {
  reasonFor = number;
  reasonChoice.innerHTML = '<option value="">Velg …</option>'
    + choices.map((c) => `<option>${esc(c)}</option>`).join("");
  reasonText.value = "";
  reasonError.textContent = "";
  document.getElementById("why-hint").textContent = "(valgfri)";
  reasonDialog.showModal();
  reasonChoice.focus();
}

reasonChoice.addEventListener("change", () => {
  document.getElementById("why-hint").textContent = reasonChoice.value === "Annet" ? "(påkrevd)" : "(valgfri)";
});

document.getElementById("why-cancel").addEventListener("click", () => {
  reasonDialog.close();
  setStatus("Journalen ble ikke åpnet.");
});

document.getElementById("why-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!reasonChoice.value) {
    reasonError.textContent = "Velg en begrunnelse.";
    return;
  }
  const reason = { begrunnelse: reasonChoice.value, forklaring: reasonText.value };
  try {
    const record = await openWithReason(reasonFor, reason);
    reasonDialog.close();
    show(reasonFor, record, reason);
  } catch (err) {
    reasonError.textContent = err.message;
  }
});

async function post(path, body, done) {
  try {
    await api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (reasonGiven) show(fnr, await openWithReason(fnr, reasonGiven), reasonGiven);
    else await openRecord(fnr);
    setStatus(done);
  } catch (e) {
    setStatus(e.message, true);
  }
}

document.getElementById("find").addEventListener("submit", (e) => {
  e.preventDefault();
  openRecord(document.getElementById("fnr").value.replace(/\s/g, ""));
});

document.getElementById("close").addEventListener("click", () => {
  fnr = null;
  reasonGiven = null;
  document.getElementById("record").hidden = true;
  document.getElementById("search").hidden = false;
  setStatus("");
});

document.getElementById("note").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = document.getElementById("note-text");
  post(`/api/pasient/${fnr}/notat`, { type: "Notat", notat: text.value }, "Notatet er lagret og delt.");
  text.value = "";
});

document.getElementById("prescribe").addEventListener("submit", (e) => {
  e.preventDefault();
  post(`/api/pasient/${fnr}/resept`, {
    legemiddel: document.getElementById("drug").value,
    dosering: document.getElementById("dose").value,
    indikasjon: document.getElementById("reason").value,
  }, "E-resepten er sendt. Pasienten ser den på Helsenorge.");
  e.target.reset();
});

whoReady.then(async (me) => {
  if (me && me.rolle !== "Lege") document.getElementById("prescribe-box").hidden = true;
  try {
    const patients = await api("/api/pasienter");
    const box = document.getElementById("patients");
    for (const p of patients) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "secondary";
      b.innerHTML = `<b>${esc(p.navn)}</b><br><span class="muted">Født ${esc(p.fodt)}</span>`;
      b.addEventListener("click", () => openRecord(p.fnr));
      box.append(b);
    }
  } catch (e) {
    setStatus(e.message, true);
  }
});
