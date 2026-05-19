// Widget de Scholarly Profile Auditor.
// Funciona en dos modos:
//   1) Standalone con backend FastAPI: POST /api/audit con FormData.
//   2) Iframe estático sin backend: lee data.json colocado junto al index.html.
//      Útil para incrustar el resultado de una auditoría ya hecha.
//
// El widget no inventa nada: refleja exactamente lo que el backend o data.json
// devuelve. Sin dependencias externas.

const API_BASE = window.SPA_API_BASE || "/api";

// --------------------------------------------------------------------------
// Utilidades
// --------------------------------------------------------------------------
function $(sel) { return document.querySelector(sel); }
function $$(sel) { return Array.from(document.querySelectorAll(sel)); }
function el(tag, attrs, children) {
  const e = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k === "html") e.innerHTML = v;
    else e.setAttribute(k, v);
  }
  if (children) for (const c of children) {
    if (typeof c === "string") e.appendChild(document.createTextNode(c));
    else if (c) e.appendChild(c);
  }
  return e;
}
function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
function trafficLight(score) {
  if (score >= 0.65) return "green";
  if (score >= 0.40) return "yellow";
  return "red";
}

// --------------------------------------------------------------------------
// Estado global del último análisis
// --------------------------------------------------------------------------
let LAST_DATA = null;

// --------------------------------------------------------------------------
// Render
// --------------------------------------------------------------------------
function showStages(stages, status) {
  $("#stages-block").classList.remove("hidden");
  const root = $("#stages");
  root.innerHTML = "";
  stages.forEach((s) => {
    const klass = s.status === "done" ? "stage" :
                  s.status === "error" ? "stage error" : "stage pending";
    const icon = s.status === "done" ? "✓" :
                 s.status === "error" ? "✗" : "…";
    root.appendChild(el("div", { class: klass },
      [el("span", { class: "icon" }, [icon]), " ", s.label]));
  });
}

function clearError() { $("#error-box").classList.add("hidden"); $("#error-box").textContent = ""; }
function showError(msg) {
  const box = $("#error-box");
  box.classList.remove("hidden");
  box.textContent = msg;
}

function renderStats(data) {
  const stats = $("#stats");
  stats.innerHTML = "";
  const items = [
    { label: "Confirmadas", value: data.counts.confirmed },
    { label: "Ambiguas", value: data.counts.ambiguous },
    { label: "Rechazadas", value: data.counts.rejected },
    { label: "Total", value: data.counts.total },
  ];
  items.forEach(({ label, value }) => {
    stats.appendChild(el("div", { class: "stat" }, [
      el("div", { class: "label" }, [label]),
      el("div", { class: "value" }, [String(value)]),
    ]));
  });
}

function renderMetrics(data) {
  const tbl = $("#metrics-table");
  tbl.innerHTML = `<thead><tr><th>Fuente</th><th>Citas</th><th>h-index</th></tr></thead>`;
  const tbody = el("tbody", {}, []);
  const sources = Object.keys(data.metrics.by_source || {});
  if (!sources.length) {
    tbody.appendChild(el("tr", {}, [el("td", { colspan: "3" }, ["Sin métricas computadas."])]));
  } else {
    sources.forEach((s) => {
      tbody.appendChild(el("tr", {}, [
        el("td", {}, [s]),
        el("td", {}, [String(data.metrics.by_source[s])]),
        el("td", {}, [String(data.metrics.h_index_by_source?.[s] ?? "—")]),
      ]));
    });
  }
  tbl.appendChild(tbody);

  // Notas
  const notesBlock = $("#metrics-notes");
  notesBlock.innerHTML = "";
  (data.metrics.notes || []).forEach((n) => {
    notesBlock.appendChild(el("div", { class: "callout" }, [n]));
  });
}

function renderYearChart(data) {
  const root = $("#year-chart");
  root.innerHTML = "";
  const byYear = data.production_by_year || {};
  const years = Object.keys(byYear).sort();
  if (!years.length) {
    root.appendChild(el("p", { class: "meta" }, ["Sin datos."]));
    return;
  }
  const counts = years.map(y => byYear[y]);
  const maxC = Math.max(...counts);
  const bars = el("div", { class: "bar-chart" }, []);
  years.forEach((y, i) => {
    const h = Math.round((counts[i] / maxC) * 100);
    const bar = el("div", { class: "bar", style: `height:${h}%` }, [
      el("span", { class: "tip" }, [`${y}: ${counts[i]}`]),
    ]);
    bars.appendChild(bar);
  });
  const labels = el("div", { class: "axis-labels" },
    years.map(y => el("span", {}, [y])));
  root.appendChild(bars);
  root.appendChild(labels);
}

function renderTypeTable(data) {
  const tbl = $("#type-table");
  tbl.innerHTML = "<thead><tr><th>Tipo</th><th>Cantidad</th></tr></thead>";
  const tbody = el("tbody", {}, []);
  Object.entries(data.production_by_type || {}).forEach(([t, n]) => {
    tbody.appendChild(el("tr", {}, [
      el("td", {}, [t]),
      el("td", {}, [String(n)]),
    ]));
  });
  tbl.appendChild(tbody);
}

function workRow(w) {
  const sources = (w.sources || []).map(s =>
    `<span class="badge src">${escapeHtml(s)}</span>`).join("");
  const cites = (w.citations_by_source || []).map(c =>
    `${escapeHtml(c.source)}: ${c.count}`).join("<br>");
  const tl = w.verification?.score != null
    ? `<span class="traffic ${trafficLight(w.verification.score)}"></span>`
    : "";
  const meta = [];
  if (w.doi) meta.push(`doi: <a href="https://doi.org/${escapeHtml(w.doi)}" target="_blank">${escapeHtml(w.doi)}</a>`);
  if (w.arxiv_id) meta.push(`arxiv: <a href="https://arxiv.org/abs/${escapeHtml(w.arxiv_id)}" target="_blank">${escapeHtml(w.arxiv_id)}</a>`);
  if (w.venue) meta.push(escapeHtml(w.venue));
  const html = `
    <td>${w.year ?? "—"}</td>
    <td>${tl}<strong>${escapeHtml(w.title)}</strong>
        ${meta.length ? `<br><span class="source-tag">${meta.join(" · ")}</span>` : ""}
    </td>
    <td>${sources}</td>
    <td>${cites || "—"}</td>
  `;
  return `<tr>${html}</tr>`;
}

function renderConfirmed(data) {
  const tbl = $("#confirmed-table");
  tbl.innerHTML = "<thead><tr><th>Año</th><th>Título</th><th>Fuentes</th><th>Citas</th></tr></thead>";
  const tbody = (data.confirmed_works || []).map(workRow).join("");
  tbl.appendChild(el("tbody", { html: tbody || `<tr><td colspan="4">— sin obras confirmadas —</td></tr>` }, []));
}

function renderRejected(data) {
  const tbl = $("#rejected-table");
  tbl.innerHTML = "<thead><tr><th>Año</th><th>Título</th><th>Fuentes</th><th>Score</th></tr></thead>";
  const rows = (data.rejected_works || []).map(w => `
    <tr>
      <td>${w.year ?? "—"}</td>
      <td>${escapeHtml(w.title)}</td>
      <td>${(w.sources || []).map(s => `<span class="badge src">${escapeHtml(s)}</span>`).join("")}</td>
      <td>${w.verification?.score?.toFixed(2) ?? "—"}</td>
    </tr>`).join("");
  tbl.appendChild(el("tbody", { html: rows || `<tr><td colspan="4">— ninguna —</td></tr>` }, []));
}

function renderAmbiguous(data) {
  const root = $("#ambiguous-list");
  root.innerHTML = "";
  const list = data.ambiguous_works || [];
  if (!list.length) { root.appendChild(el("p", { class: "meta" }, ["— ninguna —"])); return; }
  list.forEach(w => {
    const det = el("details", {}, []);
    const summary = el("summary", {}, [
      el("span", { class: `traffic ${trafficLight(w.verification?.score || 0)}` }, []),
      `${w.title} (${w.year ?? "—"}) — score ${w.verification?.score?.toFixed(2) ?? "—"}`
    ]);
    det.appendChild(summary);
    const ul = el("ul", {}, (w.verification?.reasons || []).map(r => el("li", {}, [r])));
    det.appendChild(ul);
    const meta = el("p", { class: "meta" }, [
      "Fuentes: ",
      ...(w.sources || []).map(s => el("span", { class: "badge src" }, [s])),
    ]);
    det.appendChild(meta);
    root.appendChild(det);
  });
}

function renderSnii(data) {
  const root = $("#snii-block");
  root.innerHTML = "";
  const s = data.snii_summary || {};
  if (!Object.keys(s).length) {
    root.appendChild(el("p", { class: "meta" }, ["Sin datos SNII en esta corrida."]));
    return;
  }

  root.appendChild(el("div", { class: "callout info" }, [
    el("strong", {}, ["Disclaimer. "]), s.disclaimer || ""
  ]));

  if (s.warnings && s.warnings.length) {
    const ul = el("ul", {}, s.warnings.map(w => el("li", {}, [`⚠ ${w}`])));
    root.appendChild(el("div", { class: "callout danger" }, [
      el("strong", {}, ["Advertencias"]), ul]));
  }

  root.appendChild(el("p", {}, [
    `Área usada: `, el("code", {}, [s.area_used || "—"]), ". ",
    s.area_description || ""
  ]));

  // Producción
  const prodTbl = el("table", {}, [
    el("thead", { html: "<tr><th>Producción</th><th>Cantidad</th></tr>" }, []),
    el("tbody", { html: Object.entries(s.produced_per_type || {})
      .map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${v}</td></tr>`).join("") }, []),
  ]);
  root.appendChild(prodTbl);

  // Citas por fuente
  root.appendChild(el("h3", {}, ["Citas por fuente"]));
  const citTbl = el("table", {}, [
    el("thead", { html: "<tr><th>Fuente</th><th>Citas</th><th>h-index</th></tr>" }, []),
    el("tbody", { html: Object.entries(s.citations_by_source || {})
      .map(([src, c]) =>
        `<tr><td>${escapeHtml(src)}</td><td>${c}</td><td>${s.h_index_by_source?.[src] ?? "—"}</td></tr>`)
      .join("") }, []),
  ]);
  root.appendChild(citTbl);

  // Políticas de consolidación
  root.appendChild(el("h3", {}, ["Políticas de consolidación"]));
  const policy = s.consolidation_policies || {};
  const polDiv = el("div", {}, [
    el("p", {}, [el("code", {}, ["report_per_source_only"]), " — ", policy.report_per_source_only || ""]),
    el("p", {}, [el("code", {}, ["max_per_work"]), " — ",
      policy.max_per_work?.description || "",
      el("strong", {}, [` valor: ${policy.max_per_work?.value ?? "—"}`])]),
  ]);
  root.appendChild(polDiv);

  // Umbrales si cargados
  if (s.reference_thresholds_loaded && Object.keys(s.reference_thresholds_loaded).length) {
    root.appendChild(el("h3", {}, ["Umbrales de referencia (cargados)"]));
    const thrTbl = el("table", { html:
      Object.entries(s.reference_thresholds_loaded)
        .map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${v}</td></tr>`).join("") }, []);
    root.appendChild(thrTbl);
  } else {
    root.appendChild(el("div", { class: "callout danger" }, [
      "No hay umbrales de referencia cargados. Edite ",
      el("code", {}, ["config/snii_reference_params.yaml"]),
      " con criterios oficiales vigentes."
    ]));
  }
}

function renderConflicts(data) {
  const root = $("#conflicts-list");
  root.innerHTML = "";
  const list = data.conflicts || [];
  if (!list.length) {
    root.appendChild(el("p", { class: "meta" }, ["— sin conflictos detectados —"]));
    return;
  }
  list.forEach(c => {
    const det = el("details", {}, []);
    det.appendChild(el("summary", {}, [
      el("strong", {}, [c.field]),
      ` — severidad: ${c.severity} — ${c.notes || ""}`
    ]));
    const tbl = el("table", {}, [
      el("tbody", { html: Object.entries(c.values || {})
        .map(([src, v]) => `<tr><th>${escapeHtml(src)}</th><td>${escapeHtml(v)}</td></tr>`).join("") }, [])
    ]);
    det.appendChild(tbl);
    root.appendChild(det);
  });
}

function renderAll(data) {
  LAST_DATA = data;
  $("#results").classList.remove("hidden");
  renderStats(data);
  renderMetrics(data);
  renderYearChart(data);
  renderTypeTable(data);
  renderConfirmed(data);
  renderAmbiguous(data);
  renderRejected(data);
  renderSnii(data);
  renderConflicts(data);
}

// --------------------------------------------------------------------------
// Backend
// --------------------------------------------------------------------------
async function submitAudit(formData) {
  showStages([
    { label: "Validando entrada", status: "done" },
    { label: "Consultando ORCID", status: "pending" },
    { label: "Consultando OpenAlex", status: "pending" },
    { label: "Enriqueciendo con Crossref/DataCite/arXiv", status: "pending" },
    { label: "Reconciliando y verificando autoría", status: "pending" },
    { label: "Computando métricas", status: "pending" },
  ], "running");

  const res = await fetch(`${API_BASE}/audit`, { method: "POST", body: formData });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`Backend ${res.status}: ${txt.slice(0, 300)}`);
  }
  return await res.json();
}

// --------------------------------------------------------------------------
// Export
// --------------------------------------------------------------------------
function downloadBlob(filename, content, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = el("a", { href: url, download: filename }, []);
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportJson() {
  if (!LAST_DATA) return;
  downloadBlob(`spa-${LAST_DATA.author?.orcid || "audit"}.json`,
    JSON.stringify(LAST_DATA, null, 2), "application/json");
}

function exportBib() {
  if (!LAST_DATA) return;
  const lines = [`% Generado por scholarly-profile-auditor widget`,
    `% Autor: ${LAST_DATA.author?.display_name}  ORCID: ${LAST_DATA.author?.orcid}\n`];
  (LAST_DATA.confirmed_works || []).forEach((w, i) => {
    const fa = (w.authors?.[0] || "anon").split(" ").pop().toLowerCase().replace(/[^a-z]/g, "");
    const key = `${fa || "anon"}${w.year || "n"}${i}`;
    const f = [];
    f.push(`  title = {${w.title.replace(/[{}]/g, "")}}`);
    if (w.authors?.length) f.push(`  author = {${w.authors.join(" and ")}}`);
    if (w.year) f.push(`  year = {${w.year}}`);
    if (w.venue) f.push(`  journal = {${w.venue}}`);
    if (w.doi) f.push(`  doi = {${w.doi}}`);
    if (w.arxiv_id) { f.push(`  eprint = {${w.arxiv_id}}`); f.push(`  archiveprefix = {arXiv}`); }
    const t = (w.type === "journal_article") ? "article"
            : (w.type === "book") ? "book"
            : (w.type === "book_chapter") ? "incollection"
            : (w.type === "conference_paper") ? "inproceedings"
            : "misc";
    lines.push(`@${t}{${key},\n${f.join(",\n")}\n}\n`);
  });
  downloadBlob(`spa-${LAST_DATA.author?.orcid || "audit"}.bib`,
    lines.join("\n"), "application/x-bibtex");
}

// --------------------------------------------------------------------------
// Tabs
// --------------------------------------------------------------------------
$$(".tab").forEach(t => t.addEventListener("click", () => {
  $$(".tab").forEach(x => x.classList.remove("active"));
  $$(".tab-content").forEach(x => x.classList.remove("active"));
  t.classList.add("active");
  $(`.tab-content[data-content="${t.dataset.tab}"]`).classList.add("active");
}));

// --------------------------------------------------------------------------
// Wiring
// --------------------------------------------------------------------------
$("#audit-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  clearError();
  const orcid = $("#orcid").value.trim();
  const scholar = $("#scholar").value.trim();
  const area = $("#area").value;
  const refs = $("#refs").files[0];
  if (!orcid) { showError("El ORCID es obligatorio."); return; }

  const fd = new FormData();
  fd.append("orcid", orcid);
  if (scholar) fd.append("scholar_url", scholar);
  if (area) fd.append("area_snii", area);
  if (refs) fd.append("refs", refs);

  $("#run-btn").disabled = true;
  try {
    const data = await submitAudit(fd);
    renderAll(data);
  } catch (e) {
    showError("No se pudo completar la auditoría: " + e.message);
  } finally {
    $("#run-btn").disabled = false;
  }
});

$("#export-json").addEventListener("click", exportJson);
$("#export-bib").addEventListener("click", exportBib);

// Carga demo desde data.json local (si existe).
$("#load-demo").addEventListener("click", async () => {
  clearError();
  try {
    const res = await fetch("data.json");
    if (!res.ok) throw new Error("Sin data.json al lado del index.html.");
    const data = await res.json();
    renderAll(data);
  } catch (e) {
    showError("Demo no disponible: " + e.message);
  }
});

// Auto-carga si hay ?orcid= en la URL: pasar al formulario, no submit automático
const params = new URLSearchParams(window.location.search);
if (params.get("orcid")) $("#orcid").value = params.get("orcid");
if (params.get("scholar")) $("#scholar").value = params.get("scholar");

// Modo iframe: si window.location.search incluye ?data=local intentar cargar data.json
if (params.get("data") === "local") {
  fetch("data.json").then(r => r.ok ? r.json() : null).then(d => { if (d) renderAll(d); });
}
