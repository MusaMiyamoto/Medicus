let fnr = null;
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

async function openRecord(number) {
  try {
    const record = await api(`/api/pasient/${encodeURIComponent(number)}`);
    fnr = number;
    render(record);
    document.getElementById("search").hidden = true;
    document.getElementById("record").hidden = false;
    setStatus("Tilgangen er logget. Pasienten kan se den på Helsenorge.");
  } catch (e) {
    setStatus(e.message, true);
  }
}

async function post(path, body, done) {
  try {
    await api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    await openRecord(fnr);
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
