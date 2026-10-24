const statusEl = document.getElementById("status");
let secondsLeft = null;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function list(items, fn) {
  return items.length ? items.map((x) => `<div class="item">${fn(x)}</div>`).join("") : "<p class='muted'>Ingen registrert.</p>";
}

async function show(fnr) {
  try {
    const k = await api(`/api/nod/pasient/${encodeURIComponent(fnr)}`);
    document.getElementById("name").textContent = `${k.pasient.navn} · født ${k.pasient.fodt}`;
    document.getElementById("allergies").innerHTML = list(k.allergier,
      (a) => `<b>${esc(a.stoff)}</b> – ${esc(a.reaksjon)} <span class="tag danger">${esc(a.alvorlighet)}</span>`);
    document.getElementById("conditions").innerHTML = list(k.tilstander,
      (t) => `<b>${esc(t.navn)}</b><div>${esc(t.merknad)}</div>`);
    document.getElementById("meds").innerHTML = list(k.legemidler,
      (r) => `<b>${esc(r.legemiddel)}</b> – ${esc(r.dosering)}`);
    document.getElementById("other").innerHTML =
      list(k.implantater, (i) => `<b>${esc(i.navn)}</b><div>${esc(i.merknad)}</div>`) +
      list(k.parorende, (p) => `${esc(p.navn)} (${esc(p.relasjon.toLowerCase())}), tlf. ${esc(p.telefon)}`);
    document.getElementById("search").hidden = true;
    document.getElementById("result").hidden = false;
    setStatus("Oppslaget er logget med ditt navn. Pasienten blir varslet.");
  } catch (e) {
    setStatus(e.message, true);
  }
}

function tick() {
  if (secondsLeft == null) return;
  secondsLeft = Math.max(0, secondsLeft - 1);
  const m = String(Math.floor(secondsLeft / 60)).padStart(2, "0");
  const s = String(secondsLeft % 60).padStart(2, "0");
  document.getElementById("countdown").textContent = `${m}:${s}`;
}

document.getElementById("find").addEventListener("submit", (e) => {
  e.preventDefault();
  show(document.getElementById("fnr").value.replace(/\s/g, ""));
});
document.getElementById("back").addEventListener("click", () => {
  document.getElementById("result").hidden = true;
  document.getElementById("search").hidden = false;
});
document.getElementById("end").addEventListener("click", async () => {
  await api("/api/nod/avslutt", { method: "POST" }).catch(() => {});
  setStatus("Nødtilgangen er avsluttet.");
});

whoReady.then(async (me) => {
  if (!me) return;
  secondsLeft = me.sekunder_igjen ?? null;
  if (me.situasjon) document.getElementById("reason").textContent = `Situasjon: ${me.situasjon}. `;
  tick();
  setInterval(tick, 1000);
  try {
    const patients = await api("/api/pasienter");
    const box = document.getElementById("patients");
    for (const p of patients) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "secondary";
      b.innerHTML = `<b>${esc(p.navn)}</b><br><span class="muted">Født ${esc(p.fodt)}</span>`;
      b.addEventListener("click", () => show(p.fnr));
      box.append(b);
    }
  } catch (e) {
    setStatus(e.message, true);
  }
});
