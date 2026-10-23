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

function renderNote(sections) {
  sectionsEl.innerHTML = "";
  for (const section of sections) {
    const label = document.createElement("label");
    label.htmlFor = `note-${section.key}`;
    label.textContent = section.label;
    const area = document.createElement("textarea");
    area.id = `note-${section.key}`;
    area.dataset.label = section.label;
    area.rows = 3;
    area.value = section.text;
    sectionsEl.append(label, area);
  }
  $("copy").disabled = false;
  $("approve").disabled = false;
}

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
    renderNote(data.sections);
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
  try {
    await api("/api/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: noteWithConsent() }),
    });
    setStatus("Notatet er godkjent og loggført.");
  } catch (e) {
    setStatus(e.message, true);
  }
});
