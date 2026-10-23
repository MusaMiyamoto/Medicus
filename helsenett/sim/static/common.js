// Small helpers shared by the simulator pages.

function esc(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

function when(iso) {
  const d = new Date(iso);
  return d.toLocaleString("nb-NO", { dateStyle: "medium", timeStyle: "short" });
}

function who(actor) {
  return `${esc(actor.navn)} (${esc(actor.rolle.toLowerCase())}, ${esc(actor.virksomhet)})`;
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
