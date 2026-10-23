// Shared by every Medicus page: HTML escaping, API calls, and the "who is logged in" header.

function esc(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

function when(iso) {
  return new Date(iso).toLocaleString("nb-NO", { dateStyle: "medium", timeStyle: "short" });
}

// The Medicus loading animation: a heartbeat (ECG) line with a pulse running across it.
// Shown whenever a request takes longer than a quarter of a second, the same on every page.
const EKG_PATH = "M0 26 L48 26 L52.8 23.8 L57.6 26 L67.2 26 L70.4 28.6 L75.2 4 L80 33.7 L84.8 26 " +
  "L96 26 L105.6 21.2 L115.2 26 L160 26";

function ekgSvg() {
  return `<svg class="ekg" viewBox="0 0 160 40" aria-hidden="true">
    <path class="ekg-base" d="${EKG_PATH}"/><path class="ekg-pulse" d="${EKG_PATH}" pathLength="100"/></svg>`;
}

let pending = 0;
let loaderTimer = null;
const loader = document.createElement("div");
loader.className = "loader";
loader.setAttribute("role", "status");
loader.innerHTML = `${ekgSvg()}<span>Laster …</span>`;
loader.hidden = true;
document.addEventListener("DOMContentLoaded", () => document.body.append(loader));

function loading(start) {
  pending += start ? 1 : -1;
  if (pending > 0 && !loaderTimer && loader.hidden) {
    loaderTimer = setTimeout(() => { loader.hidden = false; loaderTimer = null; }, 250);
  } else if (pending === 0) {
    clearTimeout(loaderTimer);
    loaderTimer = null;
    loader.hidden = true;
  }
}

async function api(path, options = {}) {
  loading(true);
  try {
    const response = await fetch(path, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(", ") : data.detail;
      throw new Error(detail || `Feil ${response.status}`);
    }
    return data;
  } finally {
    loading(false);
  }
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
