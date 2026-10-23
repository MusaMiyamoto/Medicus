// Medicus Post. Message text is always shown as plain text: no HTML, no clickable links in email
// from outside, and no attachments from outside.

const BADGE = {
  verifisert: '<span class="badge verifisert">✓ Verifisert</span>',
  ekstern: '<span class="badge ekstern">Ekstern</span>',
  mistenkelig: '<span class="badge mistenkelig">⚠ Mistenkelig</span>',
};
const statusEl = document.getElementById("status");
let box = "innboks";
let current = null;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function sender(m) {
  return m.kanal === "helsenett" ? m.fra.navn : `${m.fra.navn} <${m.fra.adresse}>`;
}

// A drawn paperclip: the workstation has no emoji font, so "📎" would show as an empty box.
const CLIP = `<svg class="clip" viewBox="0 0 24 24" width="14" height="14" role="img" aria-label="Har vedlegg">
  <title>Har vedlegg</title><path d="M21 11.5l-8.5 8.5a5 5 0 0 1-7-7L14 4.5a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7.5"
  fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

async function loadList() {
  const list = document.getElementById("list");
  try {
    const items = await api(`/api/post/${box}`);
    list.innerHTML = items.map((m) => `
      <li><button type="button" data-id="${m.id}" class="${m.lest ? "" : "unread"} ${current === m.id ? "active" : ""}">
        ${BADGE[m.nivå]} ${m.vedlegg ? CLIP : ""}
        <span class="from">${esc(sender(m))}</span>
        <span class="subject">${esc(m.emne)}</span>
        <span class="muted">${when(m.tid)}</span>
      </button></li>`).join("") || "<li class='muted'>Ingen meldinger.</li>";
    list.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => openMessage(Number(b.dataset.id))));
  } catch (e) {
    setStatus(e.message, true);
  }
}

function senderBanner(m) {
  if (m.kanal === "helsenett") {
    return `<div class="banner ok"><b>✓ Verifisert avsender</b><br>
      ${esc(m.fra.navn)}, ${esc(m.fra.rolle.toLowerCase())} – ${esc(m.fra.virksomhet)} (HPR ${esc(m.fra.hpr)}).
      Sendt kryptert gjennom helsenettet.</div>`;
  }
  const v = m.vurdering;
  if (v.nivå === "mistenkelig") {
    return `<div class="banner danger"><b>⚠ Dette ser ut som svindel (phishing)</b>
      <ul>${v.grunner.map((g) => `<li>${esc(g)}</li>`).join("")}</ul>
      <b>Ikke klikk på noe, ikke svar, og ikke oppgi opplysninger.</b> Trykk «Rapporter» nedenfor.</div>`;
  }
  return `<div class="banner warn"><b>Ekstern e-post</b> – fra utenfor helsenettet. Vi fant ingen tegn på svindel,
    men lenker og vedlegg er blokkert. Ekte helsetjenester ber aldri om passord, PIN eller BankID på e-post.</div>`;
}

function bodyText(m) {
  if (m.kanal === "helsenett") return `<pre class="body">${esc(m.tekst)}</pre>`;
  // External mail: show every link as text, with where it really goes.
  let text = esc(m.tekst);
  for (const link of m.vurdering.lenker) {
    const shown = esc(link.tekst);
    text = text.replace(new RegExp(`\\[${shown.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\]\\([^)]*\\)`), shown);
  }
  const links = m.vurdering.lenker.length ? `<div class="links"><b>Lenker i e-posten (ikke klikkbare):</b>
    ${m.vurdering.lenker.map((l) => `<div>«${esc(l.tekst)}» → går egentlig til <code>${esc(l.går_til)}</code></div>`).join("")}</div>` : "";
  return `<pre class="body">${text}</pre>${links}`;
}

function attachmentsHtml(m) {
  if (m.kanal === "ekstern") {
    return m.vedlegg_navn.length ? `<div class="attachments"><b>Vedlegg blokkert:</b> ${m.vedlegg_navn.map(esc).join(", ")}</div>` : "";
  }
  if (!m.vedlegg.length) return "";
  return `<div class="attachments">${m.vedlegg.map((a) => {
    const info = a.dicom ? `${esc(a.dicom.undersokelse)} · ${esc(a.dicom.modalitet)} · ${esc(a.dicom.dato)}` : esc(a.type.toUpperCase());
    const note = a.dicom && a.dicom.merknad ? `<div class="muted">${esc(a.dicom.merknad)}</div>` : "";
    const thumb = a.type === "pdf" ? '<div class="thumb pdf">PDF</div>'
      : `<img class="thumb" src="/api/post/vedlegg/${a.id}?visning=true" alt="" data-view="${a.id}" data-title="${esc(a.navn)}">`;
    const scan = a.virusskanning === "ren" ? '<div class="scan ok">✓ Virusskannet</div>'
      : '<div class="scan warn">Ikke virusskannet</div>';
    return `<div class="attachment">${thumb}<div><b>${esc(a.navn)}</b><div>${info}</div>${note}${scan}
      <a href="/api/post/vedlegg/${a.id}">Last ned</a></div></div>`;
  }).join("")}</div>`;
}

async function openMessage(id) {
  current = id;
  document.getElementById("writer").hidden = true;
  const reader = document.getElementById("reader");
  reader.hidden = false;
  try {
    const m = await api(`/api/post/${id}`);
    reader.innerHTML = `
      ${senderBanner(m)}
      <h2>${esc(m.emne)}</h2>
      <div class="muted">Fra: ${esc(sender(m))} · ${when(m.tid)}<br>Til: ${esc((m.til_navn || []).join(", "))}</div>
      ${m.fnr ? `<div class="muted">Gjelder pasient: ${esc(m.fnr.slice(0, 6))} *****</div>` : ""}
      ${bodyText(m)}
      ${attachmentsHtml(m)}
      ${m.kanal === "ekstern" ? `<p><button type="button" id="report" class="danger" ${m.rapportert ? "disabled" : ""}>
        ${m.rapportert ? "Rapportert til IT-sikkerhet" : "Rapporter til IT-sikkerhet"}</button></p>` : ""}`;
    reader.querySelectorAll("[data-view]").forEach((img) => img.addEventListener("click", () => view(img.dataset.view, img.dataset.title)));
    const report = document.getElementById("report");
    if (report) report.addEventListener("click", async () => {
      await api(`/api/post/${id}/rapporter`, { method: "POST" });
      setStatus("Takk! E-posten er rapportert. IT-sikkerhet får beskjed.");
      openMessage(id);
    });
    loadList();
  } catch (e) {
    setStatus(e.message, true);
  }
}

// Image viewer with brightness/contrast (a simple stand-in for radiology window/level).
const viewer = document.getElementById("viewer");
const viewerImg = document.getElementById("viewer-img");
let inverted = false;
function applyFilter() {
  const b = document.getElementById("brightness").value;
  const c = document.getElementById("contrast").value;
  viewerImg.style.filter = `brightness(${b}%) contrast(${c}%) ${inverted ? "invert(1)" : ""}`;
}
function view(id, title) {
  viewerImg.src = `/api/post/vedlegg/${id}?visning=true`;
  document.getElementById("viewer-title").textContent = title;
  document.getElementById("brightness").value = 100;
  document.getElementById("contrast").value = 100;
  inverted = false;
  applyFilter();
  viewer.hidden = false;
}
document.getElementById("brightness").addEventListener("input", applyFilter);
document.getElementById("contrast").addEventListener("input", applyFilter);
document.getElementById("invert").addEventListener("click", () => { inverted = !inverted; applyFilter(); });
document.getElementById("viewer-close").addEventListener("click", () => { viewer.hidden = true; });

document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {
  box = b.dataset.box;
  document.querySelectorAll(".tabs button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  loadList();
}));

document.getElementById("compose").addEventListener("click", async () => {
  document.getElementById("reader").hidden = true;
  document.getElementById("writer").hidden = false;
  const til = document.getElementById("til");
  if (!til.options.length) {
    const me = await whoReady;
    const people = await api("/api/post/adresser");
    til.innerHTML = people.filter((p) => !me || p.hpr !== me.hpr)
      .map((p) => `<option value="${esc(p.id)}">${esc(p.navn)} – ${esc(p.rolle)}, ${esc(p.virksomhet)}</option>`).join("");
    const patients = await api("/api/pasienter");
    document.getElementById("fnr").innerHTML += patients
      .map((p) => `<option value="${esc(p.fnr)}">${esc(p.navn)} (født ${esc(p.fodt)})</option>`).join("");
  }
});
document.getElementById("cancel").addEventListener("click", () => {
  document.getElementById("writer").hidden = true;
  document.getElementById("reader").hidden = false;
});

document.getElementById("send").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = new FormData();
  for (const o of document.getElementById("til").selectedOptions) form.append("til", o.value);
  form.append("emne", document.getElementById("emne").value);
  form.append("tekst", document.getElementById("tekst").value);
  form.append("fnr", document.getElementById("fnr").value);
  for (const f of document.getElementById("filer").files) form.append("filer", f);
  setStatus("Sender …");
  try {
    await api("/api/post", { method: "POST", body: form });
    e.target.reset();
    document.getElementById("writer").hidden = true;
    document.getElementById("reader").hidden = false;
    setStatus("Meldingen er sendt gjennom helsenettet.");
    box = "sendt";
    document.querySelectorAll(".tabs button").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.box === "sendt")));
    loadList();
  } catch (err) {
    setStatus(err.message, true);
  }
});

loadList();
