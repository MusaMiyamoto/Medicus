const $ = (id) => document.getElementById(id);
const transcript = $("transcript");
const sectionsEl = $("sections");
const statusEl = $("status");
let recorder = null;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Feil ${response.status}`);
  return data;
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

$("record").addEventListener("click", async () => {
  const button = $("record");
  if (recorder) {
    recorder.stop();
    return;
  }
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
      sendAudio(new Blob(chunks, { type: "audio/webm" }), "opptak.webm");
    };
    recorder.start();
    button.textContent = "■ Stopp opptak";
    button.classList.add("recording");
    setStatus("Tar opp …");
  } catch {
    setStatus("Fikk ikke tilgang til mikrofonen.", true);
  }
});

$("upload").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) sendAudio(file, file.name);
  e.target.value = "";
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

$("copy").addEventListener("click", async () => {
  await navigator.clipboard.writeText(noteText());
  setStatus("Notatet er kopiert. Lim det inn i journalsystemet.");
});

$("approve").addEventListener("click", async () => {
  try {
    await api("/api/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: noteText() }),
    });
    setStatus("Notatet er godkjent og loggført.");
  } catch (e) {
    setStatus(e.message, true);
  }
});
