const $ = (id) => document.getElementById(id);
const transcript = $("transcript");
const sectionsEl = $("sections");
const statusEl = $("status");
let recorder = null;
let discarded = false;
let consentTime = null;  // when the patient said yes, shown on the approved note
let timer = null;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

// --- Patient picker: type to search the doctor's own patients, or a fødselsnummer for anyone else ---
const search = $("patient-search");
const list = $("patient-list");
let myPatients = [];
let shown = [];      // the patients in the open list
let active = -1;     // the highlighted one (arrow keys)
let patient = null;  // the chosen patient: the approved note is saved in their record

const birth = (iso) => iso.split("-").reverse().join(".");
const masked = (fnr) => `${fnr.slice(0, 6)} *****`;

function matches(p, query) {
  const q = query.trim().toLowerCase();
  const digits = q.replace(/\D/g, "");
  return !q || p.navn.toLowerCase().includes(q) || birth(p.fodt).includes(q)
    || (digits.length >= 4 && (p.fnr.startsWith(digits) || birth(p.fodt).replace(/\D/g, "").includes(digits)));
}

function openList(on) {
  list.hidden = !on;
  search.setAttribute("aria-expanded", String(on));
  if (!on) search.removeAttribute("aria-activedescendant");
}

function highlight(index) {
  active = index;
  [...list.children].forEach((li, i) => li.setAttribute("aria-selected", String(i === index)));
  const li = list.children[index];
  if (li && li.id) {
    search.setAttribute("aria-activedescendant", li.id);
    li.scrollIntoView({ block: "nearest" });
  }
}

async function renderList() {
  const query = search.value;
  shown = myPatients.filter((p) => matches(p, query));
  const typed = query.replace(/\s/g, "");
  if (/^\d{11}$/.test(typed) && !shown.some((p) => p.fnr === typed)) {
    // Not on the doctor's list: look the number up (logged).
    try {
      shown = [{ ...(await api(`/api/journal/pasient/${typed}`)), annen: true }];
    } catch (e) {
      list.innerHTML = `<li class="empty">${esc(e.message)}</li>`;
      openList(true);
      return;
    }
  }
  list.innerHTML = shown.length
    ? shown.map((p, i) => `<li role="option" id="pasient-${i}" data-i="${i}">
        <span>${esc(p.navn)}${p.annen ? ' <span class="tag">ikke på din liste</span>' : ""}</span>
        <span class="meta">${esc(birth(p.fodt))} · ${esc(masked(p.fnr))}</span></li>`).join("")
    : `<li class="empty">Ingen treff. Skriv hele fødselsnummeret for å finne andre pasienter.</li>`;
  openList(true);
  highlight(shown.length ? 0 : -1);
}

function choose(p) {
  patient = p;
  $("chosen-name").textContent = p.navn;
  $("chosen-details").textContent = `født ${birth(p.fodt)} · ${masked(p.fnr)}`;
  $("patient-chosen").hidden = false;
  search.parentElement.hidden = true;
  openList(false);
  $("approve").textContent = "Godkjenn og lagre i journalen";
}

$("patient-clear").addEventListener("click", () => {
  patient = null;
  $("patient-chosen").hidden = true;
  search.parentElement.hidden = false;
  search.value = "";
  $("approve").textContent = "Godkjenn";
  search.focus();
});

search.addEventListener("input", renderList);
search.addEventListener("focus", renderList);
search.addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    if (list.hidden) return renderList();
    if (shown.length) highlight((active + (e.key === "ArrowDown" ? 1 : shown.length - 1)) % shown.length);
  } else if (e.key === "Enter" && !list.hidden && shown[active]) {
    e.preventDefault();
    choose(shown[active]);
  } else if (e.key === "Escape") {
    openList(false);
  }
});
list.addEventListener("mousedown", (e) => {
  const li = e.target.closest("li[data-i]");
  if (li) {
    e.preventDefault();  // keep focus in the search field
    choose(shown[Number(li.dataset.i)]);
  }
});
search.addEventListener("blur", () => openList(false));

api("/api/journal/pasienter").then((data) => {
  myPatients = data.pasienter;
  $("patient-source").textContent =
    `${myPatients.length} pasienter på listen din, fra ${data.system}. Notatet lagres i pasientens journal når du godkjenner.`;
}).catch((e) => { $("patient-source").textContent = e.message; });

async function sendAudio(blob, filename) {
  setStatus("Transkriberer … dette kan ta noen minutter på en vanlig PC.");
  const form = new FormData();
  form.append("audio", blob, filename);
  try {
    const data = await api("/api/transcribe", { method: "POST", body: form });
    transcript.value = data.transcript;
    setStatus("Transkripsjon ferdig. Les over og rett eventuelle feil.");
  } catch (e) {
    setStatus(e.message, true);
  }
}

const consent = $("consent");
const consentYes = $("consent-yes");

async function answer(svar) {
  await api("/api/samtykke", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ svar }) });
}

// "Start opptak" first asks for the patient's consent. Uploading a recording needs it too.
function askConsent(then) {
  consentYes.checked = false;
  $("consent-start").disabled = true;
  $("consent-start").onclick = async () => {
    await answer("ja");
    consentTime = new Date();
    consent.close();
    then();
  };
  consent.showModal();
}
consentYes.addEventListener("change", () => { $("consent-start").disabled = !consentYes.checked; });
$("consent-cancel").addEventListener("click", () => consent.close());
$("consent-no").addEventListener("click", async () => {
  await answer("nei");
  consentTime = null;
  consent.close();
  setStatus("Ingen opptak. Skriv samtalen inn selv, eller skriv notatet som vanlig.");
});

function showRecording(on) {
  $("recording").hidden = !on;
  clearInterval(timer);
  if (!on) return;
  const start = Date.now();
  const tick = () => {
    const s = Math.floor((Date.now() - start) / 1000);
    $("elapsed").textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  };
  tick();
  timer = setInterval(tick, 1000);
}

$("discard").addEventListener("click", async () => {
  discarded = true;
  if (recorder) recorder.stop();
  consentTime = null;
  await api("/api/samtykke", { method: "DELETE" }).catch(() => {});
  setStatus("Opptaket er slettet og ble aldri sendt. Skriv notatet som vanlig.");
});

$("record").addEventListener("click", () => {
  if (recorder) {
    recorder.stop();
    return;
  }
  askConsent(startRecording);
});

async function startRecording() {
  const button = $("record");
  discarded = false;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => chunks.push(e.data);
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      recorder = null;
      button.textContent = "● Start opptak";
      button.classList.remove("recording");
      showRecording(false);
      if (!discarded) sendAudio(new Blob(chunks, { type: "audio/webm" }), "opptak.webm");
    };
    recorder.start();
    button.textContent = "■ Stopp opptak";
    button.classList.add("recording");
    showRecording(true);
    setStatus("Tar opp …");
  } catch {
    setStatus("Fikk ikke tilgang til mikrofonen.", true);
  }
}

$("upload").addEventListener("change", (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (file) askConsent(() => sendAudio(file, file.name));
});

$("sample").addEventListener("click", async () => {
  const data = await api("/api/sample");
  transcript.value = data.transcript;
  setStatus("Eksempelsamtale lastet inn (oppdiktet).");
});

function renderNote(sections, sources) {
  sectionsEl.innerHTML = "";
  for (const section of sections) {
    const label = document.createElement("label");
    label.htmlFor = `note-${section.key}`;
    label.textContent = section.label;
    const area = document.createElement("textarea");
    area.id = `note-${section.key}`;
    area.dataset.label = section.label;
    area.dataset.key = section.key;
    area.rows = 3;
    area.value = section.text;
    area.addEventListener("input", recheckSoon);
    const list = document.createElement("ul");
    list.id = `sources-${section.key}`;
    list.className = "source-list";
    sectionsEl.append(label, area, list);
  }
  showSources(sources);
  $("copy").disabled = false;
  $("approve").disabled = false;
}

// --- Source check: where in the conversation each sentence comes from (word matching, no model) ---
let sourceCheck = null;
let recheckTimer = null;
const STATUS_TEXT = { "støttet": "✓ Sagt", "svak": "◐ Delvis", "ukjent": "✗ Ikke funnet", "mangler": "– Ikke nevnt" };

function showSources(result) {
  sourceCheck = result;
  if (!result) return;
  const lines = $("source-lines");
  lines.innerHTML = "";
  for (const line of result.linjer) {
    const item = document.createElement("li");
    item.textContent = line;
    lines.append(item);
  }
  for (const [key, items] of Object.entries(result.seksjoner)) {
    const list = $(`sources-${key}`);
    if (!list) continue;
    list.innerHTML = "";
    for (const item of items) {
      const entry = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      const missingNumbers = item.tall_uten_kilde.length > 0;
      const status = missingNumbers ? "ukjent" : item.status;
      button.className = `source-chip ${status}`;
      const chip = STATUS_TEXT[status];
      button.textContent = `${chip}  ${item.tekst}`;
      if (missingNumbers) {
        button.textContent += `  (tall ikke sagt: ${item.tall_uten_kilde.join(", ").replaceAll(".", ",")})`;
      }
      button.setAttribute("aria-label", `${chip}: ${item.tekst}`);
      button.addEventListener("click", () => highlight(item.linjer, button));
      entry.append(button);
      list.append(entry);
    }
  }
  $("source-panel").hidden = false;
  const summary = $("source-summary");
  summary.hidden = false;
  summary.classList.toggle("warning", result.uten_kilde > 0);
  summary.textContent = result.uten_kilde > 0
    ? `⚠ ${result.uten_kilde} setning(er) har ikke kilde i samtalen. Sjekk dem før du godkjenner.`
    : "✓ Alle setninger med innhold finnes i samtalen. Les likevel gjennom før du godkjenner.";
}

function highlight(lineNumbers, button) {
  document.querySelectorAll(".source-chip.active").forEach((b) => b.classList.remove("active"));
  button.classList.add("active");
  const items = [...$("source-lines").children];
  items.forEach((li, i) => li.classList.toggle("hit", lineNumbers.includes(i)));
  const first = items[lineNumbers[0]];
  if (first) first.scrollIntoView({ block: "nearest", behavior: "smooth" });
  else setStatus("Denne setningen finnes ikke i samtalen. Sjekk den, eller slett den.", true);
}

function currentSections() {
  return Object.fromEntries([...sectionsEl.querySelectorAll("textarea")].map((a) => [a.dataset.key, a.value]));
}

// After an edit, check again (it is cheap, and nothing is stored).
function recheckSoon() {
  clearTimeout(recheckTimer);
  recheckTimer = setTimeout(async () => {
    if (!sectionsEl.querySelector("textarea")) return;
    try {
      showSources(await api("/api/kildesjekk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: transcript.value, seksjoner: currentSections() }),
      }));
    } catch (e) {
      setStatus(e.message, true);
    }
  }, 600);
}
transcript.addEventListener("input", recheckSoon);

function noteText() {
  return [...sectionsEl.querySelectorAll("textarea")]
    .map((area) => `${area.dataset.label}:\n${area.value.trim()}`)
    .join("\n\n");
}

$("generate").addEventListener("click", async () => {
  if (!transcript.value.trim()) {
    setStatus("Transkripsjonen er tom.", true);
    return;
  }
  const button = $("generate");
  button.disabled = true;
  setStatus("Lager journalnotat med lokal språkmodell …");
  try {
    const data = await api("/api/note", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript: transcript.value }),
    });
    renderNote(data.sections, data.kilder);
    setStatus("Utkast klart. Kontroller alt før du godkjenner.");
  } catch (e) {
    setStatus(e.message, true);
  } finally {
    button.disabled = false;
  }
});

// When the conversation was recorded, the note says so: the patient agreed, and the audio is gone.
function noteWithConsent() {
  if (!consentTime) return noteText();
  const at = consentTime.toLocaleTimeString("nb-NO", { hour: "2-digit", minute: "2-digit" });
  return `${noteText()}\n\nLydopptak: pasienten ble informert og samtykket kl. ${at}. Opptaket er slettet etter transkribering.`;
}

$("copy").addEventListener("click", async () => {
  await navigator.clipboard.writeText(noteWithConsent());
  setStatus("Notatet er kopiert. Lim det inn i journalsystemet.");
});

$("approve").addEventListener("click", async () => {
  const unsourced = sourceCheck ? sourceCheck.uten_kilde : 0;
  if (unsourced > 0 && !confirm(`${unsourced} setning(er) har ikke kilde i samtalen (rødt under feltene).\n\n` +
      "Har du sjekket dem, og vil du godkjenne notatet likevel?")) {
    return;
  }
  try {
    const data = await api("/api/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: noteWithConsent(), fnr: patient ? patient.fnr : "" }),
    });
    setStatus(data.lagret_i
      ? `Notatet er godkjent og lagret i journalen til ${patient.navn} (${data.lagret_i}).`
      : "Notatet er godkjent og loggført. Velg pasient øverst for å lagre det i journalen.");
  } catch (e) {
    setStatus(e.message, true);
  }
});
