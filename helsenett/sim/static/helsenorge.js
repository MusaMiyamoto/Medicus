let current = null;
let currentTab = "varsler";

const TABS = {
  async varsler(fnr) {
    const events = await api(`api/innsyn/${fnr}`);
    if (!events.length) return "<p class='muted'>Ingen har åpnet journalen din.</p>";
    return "<h2>Hvem har sett journalen min</h2>" + events.map((e) => `
      <div class="item">
        ${e.modus === "nød" ? '<span class="tag danger">NØDTILGANG</span> ' : ""}
        <b>${who(e.aktor)}</b> åpnet ${esc(e.hva.toLowerCase())}
        <div class="muted">${when(e.tid)} · Begrunnelse: ${esc(e.begrunnelse)}</div>
        ${e.modus === "nød" ? '<div class="muted">Nødtilgang blir alltid kontrollert i etterkant.</div>' : ""}
      </div>`).join("");
  },
  async resepter(fnr) {
    const list = await api(`api/resepter/${fnr}`);
    if (!list.length) return "<p class='muted'>Du har ingen resepter.</p>";
    return "<h2>Resepter</h2>" + list.map((r) => `
      <div class="item">
        <b>${esc(r.legemiddel)}</b> <span class="tag ok">${esc(r.status)}</span>
        <div>${esc(r.dosering)} – ${esc(r.indikasjon)}</div>
        <div class="muted">Forskrevet av ${who(r.aktor)}, ${when(r.tid)}</div>
      </div>`).join("");
  },
  async kontakter(fnr) {
    const list = await api(`api/journal/${fnr}`);
    if (!list.length) return "<p class='muted'>Ingen registrerte besøk.</p>";
    return "<h2>Besøk og notater</h2>" + list.map((k) => `
      <div class="item">
        <b>${esc(k.type)}</b> – ${esc(k.virksomhet)}
        <div class="muted">${when(k.tid)} · ${esc(k.aktor.navn)}</div>
        <pre>${esc(k.notat)}</pre>
      </div>`).join("");
  },
  async utleveringer(fnr) {
    const list = await api(`api/utleveringer/${fnr}`);
    const intro = "<h2>Utleveringer til myndigheter</h2><p class='muted'>Opplysninger utlevert med lovhjemmel, etter vurdering hos virksomheten.</p>";
    if (!list.length) return intro + "<p class='muted'>Ingen opplysninger er utlevert.</p>";
    return intro + list.map((u) => `
      <div class="item">
        <b>${esc(u.mottaker)}</b>
        <div>Hjemmel: ${esc(u.hjemmel)}</div>
        <div>Utlevert: ${esc(u.data.join(", "))}</div>
        <div class="muted">${when(u.tid)} · Vurdert av ${esc(u.behandlet_av)}</div>
      </div>`).join("");
  },
};

async function showTab(name) {
  currentTab = name;
  document.querySelectorAll("nav button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tab === name)));
  const tab = document.getElementById("tab");
  try {
    tab.innerHTML = await TABS[name](current.fnr);
  } catch (e) {
    tab.innerHTML = `<p class="status error">${esc(e.message)}</p>`;
  }
}

async function login(person) {
  current = person;
  document.getElementById("login").hidden = true;
  document.getElementById("portal").hidden = false;
  document.getElementById("name").textContent = person.navn;
  history.replaceState(null, "", `?fnr=${person.fnr}`);
  await showTab("varsler");
}

async function init() {
  const people = await api("api/pasienter");
  const box = document.getElementById("people");
  for (const p of people) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary";
    button.innerHTML = `<b>${esc(p.navn)}</b><br><span class="muted">Født ${esc(p.fodt)}</span>`;
    button.addEventListener("click", () => login(p));
    box.append(button);
  }
  const fnr = new URLSearchParams(location.search).get("fnr");
  const match = people.find((p) => p.fnr === fnr);
  if (match) login(match);
}

document.querySelectorAll("nav button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
document.getElementById("logout").addEventListener("click", () => {
  current = null;
  history.replaceState(null, "", location.pathname);
  document.getElementById("portal").hidden = true;
  document.getElementById("login").hidden = false;
});
setInterval(() => current && showTab(currentTab), 5000);
init();
