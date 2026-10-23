const STATUS_TAG = { "Til behandling": "", Godkjent: "ok", Avslått: "danger" };

function requestCard(r) {
  const decided = r.vedtak ? `
    <div class="item">
      <b>Vedtak: ${esc(r.status)}</b> av ${esc(r.vedtak.behandlet_av)}, ${when(r.vedtak.tid)}
      <pre>${esc(r.vedtak.begrunnelse)}</pre>
      ${r.status === "Godkjent" ? `<div class="muted">${r.vedtak.varsle_pasient
        ? "Pasienten er varslet på Helsenorge."
        : "Varsel til pasienten er utsatt. Hjemmel: " + esc(r.vedtak.utsatt_varsling_hjemmel)}</div>
        <details><summary>Utleverte opplysninger</summary><pre>${esc(JSON.stringify(r.utlevert, null, 2))}</pre></details>` : ""}
    </div>` : `
    <form class="item decision" data-id="${r.id}">
      <label>Begrunnelse for vedtaket</label>
      <textarea name="begrunnelse" rows="3" required minlength="10"></textarea>
      <label>Behandlet av</label>
      <input name="behandlet_av" required placeholder="Navn og stilling (behandlingsansvarlig eller ansvarlig helsepersonell)">
      <label><input type="checkbox" name="varsle" checked style="width:auto"> Varsle pasienten på Helsenorge</label>
      <label>Hjemmel for å utsette varsel (bare hvis varsel ikke sendes)</label>
      <input name="utsatt">
      <div class="row" style="margin-top:10px">
        <button type="submit" name="beslutning" value="godkjent">Godkjenn utlevering</button>
        <button type="submit" name="beslutning" value="avslått" class="danger">Avslå</button>
      </div>
      <p class="status" role="status"></p>
    </form>`;
  return `
    <div class="card">
      <div class="row" style="justify-content:space-between">
        <h2 style="margin:0">#${r.id} ${esc(r.myndighet)}</h2>
        ${r.myndighetstype ? `<span class="muted">${esc(r.myndighetstype)}</span>` : ""}
        <span class="tag ${STATUS_TAG[r.status]}">${esc(r.status)}</span>
      </div>
      <div class="muted">${when(r.tid)} · ${esc(r.saksbehandler)}</div>
      <div><b>Pasient:</b> ${esc(r.fnr.slice(0, 6))} *****</div>
      <div><b>Hjemmel:</b> ${esc(r.hjemmel)}</div>
      <div><b>Ber om:</b> ${esc(r.data.join(", "))}${r.periode ? " · tidsrom " + esc(r.periode) : ""}</div>
      <pre>${esc(r.formal)}</pre>
      ${decided}
    </div>`;
}

let authorities = [];

// Each kind of authority only sees the legal bases that apply to it.
function showBases() {
  const chosen = authorities.find((a) => a.type === document.getElementById("myndighetstype").value);
  document.getElementById("hjemmel").innerHTML = chosen.hjemler.map((h) => `<option>${esc(h)}</option>`).join("");
  document.getElementById("merknad").textContent = chosen.merknad;
}

async function load() {
  const data = await api("/api/utlevering");
  document.getElementById("queue").innerHTML = data["forespørsler"].map(requestCard).join("")
    || "<p class='muted'>Ingen forespørsler.</p>";
  document.querySelectorAll("form.decision").forEach((form) => form.addEventListener("submit", decide));
  const types = document.getElementById("myndighetstype");
  if (!types.options.length) {
    authorities = data.myndigheter;
    types.innerHTML = authorities.map((a) => `<option>${esc(a.type)}</option>`).join("");
    types.addEventListener("change", showBases);
    showBases();
    document.getElementById("categories").innerHTML = data.kategorier.map((c) =>
      `<label style="font-weight:normal"><input type="checkbox" value="${esc(c)}" style="width:auto"> ${esc(c)}</label>`).join("");
  }
}

async function decide(event) {
  event.preventDefault();
  const form = event.target;
  const status = form.querySelector(".status");
  try {
    await api(`/api/utlevering/${form.dataset.id}/vedtak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        beslutning: event.submitter.value,
        begrunnelse: form.begrunnelse.value,
        behandlet_av: form.behandlet_av.value,
        varsle_pasient: form.varsle.checked,
        utsatt_varsling_hjemmel: form.utsatt.value,
      }),
    });
    await load();
  } catch (e) {
    status.textContent = e.message;
    status.classList.add("error");
  }
}

document.getElementById("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = document.getElementById("form-status");
  const data = [...document.querySelectorAll("#categories input:checked")].map((c) => c.value);
  try {
    const r = await api("/api/utlevering", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        myndighetstype: document.getElementById("myndighetstype").value,
        myndighet: document.getElementById("myndighet").value,
        saksbehandler: document.getElementById("saksbehandler").value,
        fnr: document.getElementById("fnr").value,
        hjemmel: document.getElementById("hjemmel").value,
        formal: document.getElementById("formal").value,
        data,
        periode: document.getElementById("periode").value,
      }),
    });
    status.textContent = `Forespørsel #${r.id} er sendt og venter på behandling.`;
    status.classList.remove("error");
    event.target.reset();
    showBases();
    await load();
  } catch (e) {
    status.textContent = e.message;
    status.classList.add("error");
  }
});

document.querySelectorAll("nav button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("nav button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  document.getElementById("behandle").hidden = b.dataset.view !== "behandle";
  document.getElementById("ny").hidden = b.dataset.view !== "ny";
}));
load();
