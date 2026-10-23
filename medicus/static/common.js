// Shared by every Medicus page: HTML escaping, API calls, and the "who is logged in" header.

function esc(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

function when(iso) {
  return new Date(iso).toLocaleString("nb-NO", { dateStyle: "medium", timeStyle: "short" });
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(", ") : data.detail;
    throw new Error(detail || `Feil ${response.status}`);
  }
  return data;
}

async function showWho() {
  const box = document.getElementById("who");
  try {
    const me = await api("/api/meg");
    box.innerHTML = `<b>${esc(me.navn)}</b><br>${esc(me.rolle)} · ${esc(me.virksomhet)}`;
    return me;
  } catch (e) {
    box.textContent = e.message;
    return null;
  }
}

const whoReady = showWho();
