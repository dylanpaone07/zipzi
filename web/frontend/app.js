/* Zipzi frontend — SPA estática sin build. Routing por hash.
   API (mismo origen, base /api): meta, profiles, matches, connections. */
"use strict";

const LS_KEY = "zipzi_my_profile_id";

const vista = document.getElementById("vista");
const modalRoot = document.getElementById("modal-root");
const toastEl = document.getElementById("toast");

const state = {
  meta: null,
  profiles: [],
  matches: [],
  matchesById: {},
  connections: [],
  myProfileId: localStorage.getItem(LS_KEY),
  filters: { q: "", disponibilidad: "", habilidad: "", interes: "" },
  filtersOpen: false,
  myProfile: null,
  quiz: null,
};

const GRADIENTS = [
  "linear-gradient(135deg,#3b2d6e,#8a4b8f)",
  "linear-gradient(135deg,#5a2d4e,#c65d3b)",
  "linear-gradient(135deg,#1f4e5f,#3b8a6e)",
  "linear-gradient(135deg,#6e3b2d,#c6a23b)",
  "linear-gradient(135deg,#2d3b6e,#6e5fc6)",
  "linear-gradient(135deg,#4e2d5f,#b04b8a)",
];

const SLIDERS = [
  { key: "apetito_riesgo", label: "Apetito de riesgo", min: "Muy conservador", max: "Muy arriesgado" },
  { key: "estilo_decision", label: "Estilo de decisión", min: "Muy analítico", max: "Muy intuitivo" },
  { key: "confianza", label: "Confianza", min: "Reservado", max: "Muy abierto" },
  { key: "energia", label: "Energía", min: "Tranquila", max: "Intensa" },
  { key: "disciplina", label: "Disciplina", min: "Flexible", max: "Muy metódico" },
  { key: "creatividad", label: "Creatividad", min: "Práctico", max: "Muy creativo" },
  { key: "inversion_dinero", label: "Inversión de dinero", min: "Nada", max: "Mucho" },
];

const QUIZ_STEPS = ["Vos", "Tu visión", "Skills", "Tu estilo", "Revisá"];

/* ---------- utilidades ---------- */
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function initials(nombre) {
  return String(nombre || "?")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");
}

function gradientFor(id) {
  let h = 0;
  const s = String(id || "?");
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 997;
  return GRADIENTS[h % GRADIENTS.length];
}

function debounce(fn, ms) {
  let t;
  return (...a) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...a), ms);
  };
}

let toastTimer;
function toast(msg) {
  toastEl.textContent = msg;
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.hidden = true; }, 3200);
}

/* ---------- API ---------- */
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail || ""; } catch (e) { /* noop */ }
    throw new Error(detail || `Error ${res.status} en ${path}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function apiErrorHTML(err) {
  return `<div class="error-banner" role="alert">
    No pudimos conectar con el servidor de Zipzi (${esc(err.message || "error desconocido")}).
    Revisá que el backend esté corriendo e intentá de nuevo.
  </div>`;
}

/* ---------- anillo de score (SVG) ---------- */
function ring(pct, size, opts = {}) {
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const color = opts.color || "var(--coral)";
  const title = opts.title ? ` title="${esc(opts.title)}"` : "";
  const label = opts.title || `Compatibilidad ${p}%`;
  return `<svg class="ring" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"
      role="img" aria-label="${esc(label)}"${title}>
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none"
      stroke="rgba(255,255,255,.10)" stroke-width="6"/>
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none"
      stroke="${color}" stroke-width="6" stroke-linecap="round"
      stroke-dasharray="${((p / 100) * c).toFixed(1)} ${c.toFixed(1)}"
      transform="rotate(-90 ${size / 2} ${size / 2})"/>
    <text x="50%" y="50%" dy=".35em" text-anchor="middle" font-size="${Math.round(size * 0.28)}">${p}</text>
  </svg>`;
}

function dispDotClass(d) {
  const v = String(d || "").toLowerCase();
  if (v === "disponible") return "dot-green";
  if (v === "selectivo") return "dot-gold";
  return "dot-gray";
}

/* ---------- carga de datos ---------- */
async function loadMeta() {
  if (state.meta) return state.meta;
  state.meta = await api("/api/meta");
  return state.meta;
}

async function loadProfiles() {
  const f = state.filters;
  const qs = new URLSearchParams();
  if (f.q) qs.set("q", f.q);
  if (f.disponibilidad) qs.set("disponibilidad", f.disponibilidad);
  if (f.habilidad) qs.set("habilidad", f.habilidad);
  if (f.interes) qs.set("interes", f.interes);
  const q = qs.toString();
  state.profiles = await api("/api/profiles" + (q ? "?" + q : ""));
  return state.profiles;
}

async function loadMatches() {
  if (!state.myProfileId) return [];
  state.matches = await api(`/api/matches?profile_id=${encodeURIComponent(state.myProfileId)}`);
  state.matchesById = {};
  for (const m of state.matches) {
    if (m.profile && m.profile.id) state.matchesById[m.profile.id] = m;
  }
  return state.matches;
}

async function loadConnections() {
  if (!state.myProfileId) { state.connections = []; return []; }
  state.connections = await api(`/api/connections?profile_id=${encodeURIComponent(state.myProfileId)}`);
  return state.connections;
}

async function loadMyProfile() {
  if (!state.myProfileId) { state.myProfile = null; return null; }
  try {
    state.myProfile = await api(`/api/profiles/${encodeURIComponent(state.myProfileId)}`);
  } catch (e) {
    state.myProfile = null; // id local inválido: se limpia abajo al renderizar
  }
  return state.myProfile;
}

/* ---------- router ---------- */
const ROUTES = { descubrir: "descubrir", conexiones: "conexiones", perfil: "perfil" };

function currentRoute() {
  const h = (location.hash || "").replace(/^#\/?/, "").split("?")[0];
  return ROUTES[h] || "descubrir";
}

function markNav(route) {
  document.querySelectorAll("[data-nav]").forEach((a) => {
    a.classList.toggle("active", a.dataset.nav === route);
  });
}

window.addEventListener("hashchange", render);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && modalRoot.firstChild) closeModal();
});

async function render() {
  const route = currentRoute();
  markNav(route);
  closeModal(true);
  vista.innerHTML = `<div class="spinner" role="status" aria-label="Cargando"></div>`;
  try {
    if (route === "descubrir") await renderDescubrir();
    else if (route === "conexiones") await renderConexiones();
    else await renderPerfil();
  } catch (err) {
    vista.innerHTML = apiErrorHTML(err);
  }
  window.scrollTo(0, 0);
}

/* ---------- vista: descubrir ---------- */
async function renderDescubrir() {
  await loadMeta();
  await loadProfiles();
  if (state.myProfileId) {
    try { await loadMatches(); } catch (e) { /* sin matches, se muestran tarjetas igual */ }
  }

  const f = state.filters;
  const meta = state.meta;

  const dispOpts = ["", ...(meta.disponibilidades || [])];
  const dispSeg = dispOpts.map((d) =>
    `<button type="button" class="seg${f.disponibilidad === d ? " active" : ""}"
      data-f="disponibilidad" data-v="${esc(d)}">${d === "" ? "Todos" : esc(d)}</button>`
  ).join("");

  const habChips = (meta.skills || []).map((s) =>
    `<button type="button" class="chip${f.habilidad === s ? " active" : ""}"
      data-f="habilidad" data-v="${esc(s)}">${esc(s)}</button>`
  ).join("");

  const intChips = (meta.intereses || []).map((s) =>
    `<button type="button" class="chip chip-gold${f.interes === s ? " active" : ""}"
      data-f="interes" data-v="${esc(s)}">${esc(s)}</button>`
  ).join("");

  vista.innerHTML = `
    <section class="hero">
      <h1>Encontrá tu <span class="accent">equipo maestro</span></h1>
      <p>No filtramos por CV. Conectamos por visión, intereses y lo que querés construir.</p>
    </section>

    ${state.myProfileId ? "" : `
    <div class="cta-banner">
      <p><strong>Completá tu perfil</strong> para ver tu compatibilidad con cada persona.</p>
      <a class="btn btn-primary" href="#/perfil">Crear mi perfil</a>
    </div>`}

    <div class="search-row">
      <input id="q" class="search-input" type="search" autocomplete="off"
        placeholder="Buscá por visión, habilidad, proyecto, interés..."
        value="${esc(f.q)}" aria-label="Buscar personas">
      <button id="btn-filtros" class="btn btn-ghost" aria-expanded="${state.filtersOpen}">Filtros</button>
    </div>

    <div id="filters-panel" class="filters-panel${state.filtersOpen ? " open" : ""}">
      <div class="filter-group">
        <span class="filter-label">Disponibilidad</span>
        <div class="seg-row">${dispSeg}</div>
      </div>
      <div class="filter-group">
        <span class="filter-label">Habilidades</span>
        <div class="chips">${habChips || "<span style='color:var(--muted)'>—</span>"}</div>
      </div>
      <div class="filter-group">
        <span class="filter-label">Intereses</span>
        <div class="chips">${intChips || "<span style='color:var(--muted)'>—</span>"}</div>
      </div>
      <div class="filters-actions">
        <button id="btn-limpiar" class="link-btn" type="button">Limpiar filtros</button>
      </div>
    </div>

    <p class="result-count"><strong>${state.profiles.length}</strong> persona${state.profiles.length === 1 ? "" : "s"} encontrada${state.profiles.length === 1 ? "" : "s"}</p>

    <div id="cards" class="cards-grid"></div>
    <div id="cards-empty"></div>
  `;

  // buscador
  const qInput = document.getElementById("q");
  const onSearch = debounce(() => {
    state.filters.q = qInput.value.trim();
    refreshCards();
  }, 450);
  qInput.addEventListener("input", onSearch);
  qInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); state.filters.q = qInput.value.trim(); refreshCards(); }
  });

  document.getElementById("btn-filtros").addEventListener("click", (e) => {
    state.filtersOpen = !state.filtersOpen;
    document.getElementById("filters-panel").classList.toggle("open", state.filtersOpen);
    e.currentTarget.setAttribute("aria-expanded", String(state.filtersOpen));
  });

  document.getElementById("btn-limpiar").addEventListener("click", () => {
    state.filters = { q: "", disponibilidad: "", habilidad: "", interes: "" };
    renderDescubrir();
  });

  vista.querySelectorAll("[data-f]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const k = btn.dataset.f, v = btn.dataset.v;
      state.filters[k] = state.filters[k] === v ? "" : v; // toggle
      renderDescubrir();
    });
  });

  paintCards();
}

async function refreshCards() {
  try {
    await loadProfiles();
  } catch (err) {
    document.getElementById("cards").innerHTML = "";
    document.getElementById("cards-empty").innerHTML = apiErrorHTML(err);
    return;
  }
  document.querySelector(".result-count").innerHTML =
    `<strong>${state.profiles.length}</strong> persona${state.profiles.length === 1 ? "" : "s"} encontrada${state.profiles.length === 1 ? "" : "s"}`;
  paintCards();
}

function scoreRingForCard(p) {
  if (!state.myProfileId) return "";
  const m = state.matchesById[p.id];
  if (!m) return "";
  const pct = Math.round((m.total || 0) * 100);
  if (m.pasa_filtros) {
    return `<span class="card-ring" title="Compatibilidad: ${pct}%">${ring(pct, 56)}</span>`;
  }
  return `<span class="card-ring" title="Descartado: ${esc(m.motivo_descarte || "no pasa los filtros duros")}">${ring(pct, 56, { color: "var(--gray-dot)", title: "Descartado: " + (m.motivo_descarte || "filtros duros") })}</span>`;
}

function cardHTML(p) {
  const skills = (p.skills_ofrece || []).slice(0, 3);
  const extra = (p.skills_ofrece || []).length - skills.length;
  return `
  <article class="card" data-id="${esc(p.id)}" tabindex="0" role="button"
      aria-label="Ver perfil de ${esc(p.nombre)}">
    <div class="card-photo" style="background:${gradientFor(p.id)}">
      <span class="badge-disp"><span class="dot ${dispDotClass(p.disponibilidad)}"></span>${esc(p.disponibilidad || "—")}</span>
      ${scoreRingForCard(p)}
      <span class="initials" aria-hidden="true">${esc(initials(p.nombre))}</span>
    </div>
    <div class="card-body">
      <h3 class="card-name">${esc(p.nombre)}</h3>
      <p class="card-meta">${esc(p.edad)} · ${esc(p.ciudad)}</p>
      ${p.tagline ? `<p class="card-tagline">“${esc(p.tagline)}”</p>` : ""}
      ${p.bio ? `<p class="card-bio">${esc(p.bio)}</p>` : ""}
      <div class="card-tags">
        ${skills.map((s) => `<span class="tag tag-skill">${esc(s)}</span>`).join("")}
        ${extra > 0 ? `<span class="tag tag-more">+${extra}</span>` : ""}
      </div>
    </div>
  </article>`;
}

function paintCards() {
  const grid = document.getElementById("cards");
  const empty = document.getElementById("cards-empty");
  if (!state.profiles.length) {
    grid.innerHTML = "";
    empty.innerHTML = `<div class="empty-state">
      <h2>Nada por acá… todavía</h2>
      <p>No encontramos personas con esos filtros. Probá ampliando la búsqueda.</p>
      <button class="btn btn-ghost" id="btn-limpiar2" type="button">Limpiar filtros</button>
    </div>`;
    document.getElementById("btn-limpiar2").addEventListener("click", () => {
      state.filters = { q: "", disponibilidad: "", habilidad: "", interes: "" };
      renderDescubrir();
    });
    return;
  }
  empty.innerHTML = "";
  grid.innerHTML = state.profiles.map(cardHTML).join("");
  grid.querySelectorAll(".card").forEach((c) => {
    c.addEventListener("click", () => openModal(c.dataset.id));
    c.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openModal(c.dataset.id); }
    });
  });
}

/* ---------- modal de perfil ---------- */
async function openModal(id) {
  modalRoot.innerHTML = `<div class="modal-overlay"><div class="modal" role="dialog" aria-modal="true" aria-label="Perfil">
    <div class="spinner"></div></div></div>`;
  const overlay = modalRoot.firstChild;
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });

  try {
    const p = await api(`/api/profiles/${encodeURIComponent(id)}`);
    if (state.myProfileId && !state.matches.length) {
      try { await loadMatches(); } catch (e) { /* sin matches */ }
    }
    const match = state.matchesById[id] || null;
    modalRoot.querySelector(".modal").outerHTML = modalHTML(p, match);
    wireModal(p, match);
  } catch (err) {
    modalRoot.querySelector(".modal").innerHTML = `
      <div class="modal-body">${apiErrorHTML(err)}
        <button class="btn btn-ghost modal-close-x2" type="button">Cerrar</button>
      </div>`;
    modalRoot.querySelector(".modal-close-x2").addEventListener("click", closeModal);
  }
}

function closeModal(silent) {
  modalRoot.innerHTML = "";
  document.body.style.overflow = "";
}

function traitBar(t) {
  const pct = Math.round((t.coincidencia || 0) * 100);
  const peso = t.peso != null ? Math.round(t.peso * 100) + "%" : "—";
  return `<div class="trait">
    <div class="trait-head"><span class="trait-name">${esc(t.label || t.key)}</span>
    <span class="trait-meta">${pct}% · peso ${peso}</span></div>
    <div class="bar" role="img" aria-label="${esc(t.label || t.key)}: ${pct}%"><div class="bar-fill" style="width:${pct}%"></div></div>
  </div>`;
}

function compatHTML(m) {
  if (!m) return "";
  const total = Math.round((m.total || 0) * 100);
  const personal = Math.round((m.compatibilidad_personal || 0) * 100);
  const necesidad = Math.round((m.necesidad || 0) * 100);

  const hardFilters = m.pasa_filtros
    ? `<div class="hard-filters">
        <span class="hf-badge hf-ok">✓ Idioma</span>
        <span class="hf-badge hf-ok">✓ Zona horaria</span>
        <span class="hf-badge hf-ok">✓ Disponibilidad</span>
      </div>`
    : `<div class="hard-filters">
        <span class="hf-badge hf-bad">Descartado: ${esc(m.motivo_descarte || "filtros duros")}</span>
      </div>`;

  const personalTraits = (m.desglose && m.desglose.personal_traits) || [];
  const necesidadTraits = (m.desglose && m.desglose.necesidad_traits) || [];

  return `
  <section class="compat-box" aria-label="Compatibilidad con vos">
    <div class="compat-head">
      ${ring(total, 84, { color: m.pasa_filtros ? "var(--coral)" : "var(--gray-dot)" })}
      <div class="compat-total">
        <strong>Compatibilidad con vos</strong>
        <span>${m.pasa_filtros ? "Calculada con el motor de matching de Zipzi" : "No pasa los filtros duros, igual te mostramos el desglose"}</span>
      </div>
    </div>
    ${hardFilters}
    <div class="compat-block">
      <div class="compat-block-title"><h4>Afinidad personal</h4><span class="block-score">${personal}%</span></div>
      ${personalTraits.map(traitBar).join("") || `<p style="color:var(--muted)">Sin datos.</p>`}
    </div>
    <div class="compat-block">
      <div class="compat-block-title"><h4>Necesidad funcional</h4><span class="block-score">${necesidad}%</span></div>
      ${necesidadTraits.map(traitBar).join("") || `<p style="color:var(--muted)">Sin datos.</p>`}
    </div>
    <div class="compat-foot">
      <strong>Similitud de objetivos: ${m.similitud_objetivos_pct != null ? Math.round(m.similitud_objetivos_pct) + "%" : "—"}${
        m.similitud_objetivos_categoria ? ` (${esc(m.similitud_objetivos_categoria)})` : ""}</strong>
      ${m.ajuste_objetivo != null && m.ajuste_objetivo !== "" ? `<span class="ajuste">Ajuste por objetivo: ${esc(String(m.ajuste_objetivo))}</span>` : ""}
    </div>
  </section>`;
}

function modalHTML(p, match) {
  const tags = (arr, cls) => (arr || []).map((t) => `<span class="tag ${cls}">${esc(t)}</span>`).join("");
  const section = (label, inner) => inner
    ? `<div class="modal-section"><span class="mini-label">${label}</span>${inner}</div>` : "";
  const numList = (arr) => (arr && arr.length)
    ? `<ol class="num-list">${arr.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>` : "";

  const isSelf = state.myProfileId && String(state.myProfileId) === String(p.id);

  return `
  <div class="modal" role="dialog" aria-modal="true" aria-label="Perfil de ${esc(p.nombre)}">
    <button class="modal-close" type="button" aria-label="Cerrar">✕</button>
    <div class="modal-photo" style="background:${gradientFor(p.id)}">
      <span class="badge-disp"><span class="dot ${dispDotClass(p.disponibilidad)}"></span>${esc(p.disponibilidad || "—")}</span>
      <span class="initials" aria-hidden="true">${esc(initials(p.nombre))}</span>
    </div>
    <div class="modal-body">
      <h2 class="modal-name">${esc(p.nombre)}</h2>
      <p class="modal-meta">${esc(p.edad)} · ${esc(p.ciudad)}${p.idioma ? ` · ${esc(p.idioma)}` : ""}</p>
      ${p.tagline ? `<p class="modal-quote">“${esc(p.tagline)}”</p>` : ""}

      ${state.myProfileId && !isSelf ? compatHTML(match) : ""}

      ${section("Sobre mí", p.bio ? `<p>${esc(p.bio)}</p>` : "")}
      ${section("Visión a largo plazo", p.vision ? `<p>${esc(p.vision)}</p>` : "")}
      ${section("Habilidades", tags(p.skills_ofrece, "tag-skill"))}
      ${section("Intereses", tags(p.intereses, "tag-interest"))}
      ${section("Mis objetivos", numList(p.objetivos_lista))}
      ${section("Mis proyectos", numList(p.proyectos_lista))}
      ${section("Quién busco", p.quien_busco ? `<p>${esc(p.quien_busco)}</p>` : "")}

      ${isSelf ? "" : `
      <div class="modal-actions">
        <button class="btn btn-primary" id="btn-conectar" type="button">Conectar con ${esc(p.nombre.split(" ")[0])}</button>
        <button class="btn btn-ghost" id="btn-guardar" type="button">Guardar</button>
      </div>`}
    </div>
  </div>`;
}

function existingConnection(toId, action) {
  return state.connections.find((c) => String(c.profile?.id) === String(toId) && c.action === action);
}

function wireModal(p, match) {
  const overlay = modalRoot.querySelector(".modal-overlay");
  document.body.style.overflow = "hidden";
  modalRoot.querySelector(".modal-close").addEventListener("click", closeModal);

  const btnC = document.getElementById("btn-conectar");
  const btnS = document.getElementById("btn-guardar");
  if (!btnC || !btnS) return;

  const goQuiz = () => {
    closeModal();
    toast("Creá tu perfil para poder conectar");
    location.hash = "#/perfil";
  };

  // estado inicial según conexiones existentes
  const ec = existingConnection(p.id, "connect");
  const es = existingConnection(p.id, "save");
  if (ec) { btnC.textContent = "¡Conectado!"; btnC.classList.add("btn-done"); btnC.disabled = true; }
  if (es) { btnS.textContent = "Guardado"; btnS.classList.add("btn-done"); btnS.disabled = true; }

  async function doAction(action, btn, doneLabel) {
    if (!state.myProfileId) { goQuiz(); return; }
    if (existingConnection(p.id, action)) return;
    btn.disabled = true;
    try {
      const conn = await api("/api/connections", {
        method: "POST",
        body: JSON.stringify({ from_id: state.myProfileId, to_id: p.id, action }),
      });
      state.connections.push(conn);
      btn.textContent = doneLabel;
      btn.classList.add("btn-done");
      toast(action === "connect" ? `¡Conexión enviada a ${p.nombre}!` : `${p.nombre} guardado en tu lista`);
    } catch (err) {
      btn.disabled = false;
      toast("No se pudo completar la acción. Intentá de nuevo.");
    }
  }

  btnC.addEventListener("click", () => doAction("connect", btnC, "¡Conectado!"));
  btnS.addEventListener("click", () => doAction("save", btnS, "Guardado"));
}

/* ---------- vista: conexiones ---------- */
async function renderConexiones() {
  if (!state.myProfileId) {
    vista.innerHTML = `<div class="vista-narrow" style="margin:0 auto">
      <div class="empty-state">
        <h2>Tus conexiones viven acá</h2>
        <p>Primero creá tu perfil para empezar a conectar con personas.</p>
        <a class="btn btn-primary" href="#/perfil">Crear mi perfil</a>
      </div>
    </div>`;
    return;
  }
  await loadConnections();
  const connects = state.connections.filter((c) => c.action === "connect");
  const saves = state.connections.filter((c) => c.action === "save");

  const itemHTML = (c) => {
    const p = c.profile || {};
    return `<div class="conn-item" data-id="${esc(p.id)}" data-conn="${esc(c.id)}" tabindex="0" role="button"
        aria-label="Ver perfil de ${esc(p.nombre)}">
      <span class="conn-avatar" style="background:${gradientFor(p.id)}" aria-hidden="true">${esc(initials(p.nombre))}</span>
      <span class="conn-info"><strong>${esc(p.nombre)}</strong>
        <span>${esc(p.tagline || p.bio || "")}</span></span>
      <button class="btn-quitar" type="button" data-quitar="${esc(c.id)}">Quitar</button>
    </div>`;
  };

  const groupHTML = (title, list, emptyMsg) => `
    <section class="conn-group">
      <h2>${title} (${list.length})</h2>
      ${list.length ? `<div class="conn-list">${list.map(itemHTML).join("")}</div>`
        : `<div class="empty-state" style="padding:2rem 1rem"><p>${emptyMsg}</p></div>`}
    </section>`;

  vista.innerHTML = `<div class="vista-narrow" style="margin:0 auto">
    ${(!connects.length && !saves.length) ? `<div class="empty-state">
      <h2>Todavía no tenés conexiones</h2>
      <p>Explorá personas en Descubrir y tocá “Conectar” o “Guardar” en su perfil.</p>
      <a class="btn btn-primary" href="#/descubrir">Descubrir personas</a>
    </div>` : ""}
    ${groupHTML("Conexiones", connects, "Todavía no conectaste con nadie.")}
    ${groupHTML("Guardados", saves, "Todavía no guardaste a nadie.")}
  </div>`;

  vista.querySelectorAll(".conn-item").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (e.target.closest("[data-quitar]")) return;
      openModal(el.dataset.id);
    });
    el.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && !e.target.closest("[data-quitar]")) {
        e.preventDefault(); openModal(el.dataset.id);
      }
    });
  });

  vista.querySelectorAll("[data-quitar]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const cid = btn.dataset.quitar;
      btn.disabled = true;
      try {
        await api(`/api/connections/${encodeURIComponent(cid)}`, { method: "DELETE" });
        state.connections = state.connections.filter((c) => String(c.id) !== String(cid));
        toast("Eliminado de tu lista");
        renderConexiones();
      } catch (err) {
        btn.disabled = false;
        toast("No se pudo quitar. Intentá de nuevo.");
      }
    });
  });
}

/* ---------- vista: perfil ---------- */
async function renderPerfil() {
  await loadMyProfile().catch(() => null);
  if (state.myProfileId && !state.myProfile) {
    // id local inválido: limpiar y arrancar cuestionario
    localStorage.removeItem(LS_KEY);
    state.myProfileId = null;
  }
  if (!state.myProfileId) {
    if (!state.quiz) state.quiz = newQuiz();
    renderQuiz();
  } else {
    state.quiz = null;
    await renderOwnProfile();
  }
}

/* ----- cuestionario ----- */
function newQuiz() {
  return {
    step: 0,
    data: {
      nombre: "", edad: "", ciudad: "", idioma: "", timezone: "", horas_semana: "",
      tagline: "", bio: "", vision: "", objetivo: "",
      rubro: [], orientacion: [], quien_busco: "",
      skills_ofrece: [], skills_busca: [], intereses: [],
      rasgos: { apetito_riesgo: 3, estilo_decision: 3, confianza: 3, energia: 3, disciplina: 3, creatividad: 3 },
      inversion_dinero: 3, horizonte_meses: "",
      objetivos_lista: [], proyectos_lista: [],
    },
  };
}

function chipGroupHTML(label, group, options, selected, gold) {
  return `<div class="field"><span class="field-label">${label}</span>
    <div class="chips" data-chips="${group}">
      ${options.map((o) => `<button type="button" class="chip${gold ? " chip-gold" : ""}${selected.includes(o) ? " active" : ""}"
        data-group="${group}" data-v="${esc(o)}">${esc(o)}</button>`).join("")}
    </div>
    <div class="chip-input-row">
      <input type="text" data-custom="${group}" placeholder="Otro… (Enter para agregar)" aria-label="Agregar ${label.toLowerCase()} personalizado">
      <button type="button" data-add="${group}">Agregar</button>
    </div>
  </div>`;
}

function quizStepHTML() {
  const q = state.quiz, d = q.data, meta = state.meta;
  const val = (k) => esc(d[k] || "");

  if (q.step === 0) return `
    <div class="field-row">
      <div class="field"><label for="f-nombre">Nombre *</label>
        <input id="f-nombre" type="text" data-k="nombre" value="${val("nombre")}" placeholder="¿Cómo te llamás?" required></div>
      <div class="field"><label for="f-edad">Edad</label>
        <input id="f-edad" type="number" data-k="edad" value="${val("edad")}" min="14" max="120" placeholder="Ej: 24"></div>
    </div>
    <div class="field"><label for="f-ciudad">Ciudad</label>
      <input id="f-ciudad" type="text" data-k="ciudad" value="${val("ciudad")}" placeholder="Ej: Buenos Aires"></div>
    <div class="field-row">
      <div class="field"><label for="f-idioma">Idioma</label>
        <select id="f-idioma" data-k="idioma">
          <option value="">Elegí…</option>
          ${(meta.idiomas || []).map((i) => `<option value="${esc(i)}"${d.idioma === i ? " selected" : ""}>${esc(i)}</option>`).join("")}
        </select></div>
      <div class="field"><label for="f-tz">Zona horaria</label>
        <select id="f-tz" data-k="timezone">
          <option value="">Elegí…</option>
          ${(meta.timezones || []).map((t) => `<option value="${esc(t)}"${d.timezone === t ? " selected" : ""}>${esc(t)}</option>`).join("")}
        </select></div>
    </div>
    <div class="field"><label for="f-horas">Horas por semana que le podés dedicar</label>
      <input id="f-horas" type="number" data-k="horas_semana" value="${val("horas_semana")}" min="0" max="168" placeholder="Ej: 10"></div>`;

  if (q.step === 1) return `
    <div class="field"><label for="f-tagline">Tu frase (tagline)</label>
      <input id="f-tagline" type="text" data-k="tagline" value="${val("tagline")}" placeholder="Ej: Construyo productos que la gente ama"></div>
    <div class="field"><label for="f-bio">Contanos sobre vos</label>
      <textarea id="f-bio" data-k="bio" placeholder="¿Quién sos? ¿Qué hacés? ¿Qué te mueve?">${val("bio")}</textarea></div>
    <div class="field"><label for="f-vision">Tu visión a largo plazo</label>
      <textarea id="f-vision" data-k="vision" placeholder="¿A dónde querés llegar en 5-10 años?">${val("vision")}</textarea></div>
    <div class="field"><label for="f-objetivo">¿Qué querés construir?</label>
      <select id="f-objetivo" data-k="objetivo">
        <option value="">Elegí…</option>
        ${(meta.objetivos || []).map((o) => `<option value="${esc(o)}"${d.objetivo === o ? " selected" : ""}>${esc(o)}</option>`).join("")}
      </select></div>
    ${chipGroupHTML("Rubro", "rubro", meta.rubros || [], d.rubro)}
    ${chipGroupHTML("Orientación", "orientacion", meta.orientaciones || [], d.orientacion)}
    <div class="field"><label for="f-busco">¿A quién buscás?</label>
      <textarea id="f-busco" data-k="quien_busco" placeholder="Describí a tu socio/a ideal…">${val("quien_busco")}</textarea></div>`;

  if (q.step === 2) return `
    ${chipGroupHTML("¿Qué habilidades ofrecés?", "skills_ofrece", meta.skills || [], d.skills_ofrece)}
    ${chipGroupHTML("¿Qué habilidades buscás en un socio?", "skills_busca", meta.skills || [], d.skills_busca)}
    ${chipGroupHTML("Tus intereses", "intereses", meta.intereses || [], d.intereses, true)}`;

  if (q.step === 3) {
    const rasgos = d.rasgos;
    return SLIDERS.map((s) => {
      const cur = s.key === "inversion_dinero" ? d.inversion_dinero : rasgos[s.key];
      return `<div class="slider-field">
        <div class="slider-top"><label for="sl-${s.key}">${s.label}</label>
          <span class="slider-val" id="sv-${s.key}">${cur}</span></div>
        <input type="range" id="sl-${s.key}" data-slider="${s.key}" min="1" max="5" step="1" value="${cur}"
          aria-label="${s.label}: 1 ${s.min}, 5 ${s.max}">
        <div class="slider-ends"><span>1 · ${s.min}</span><span>5 · ${s.max}</span></div>
      </div>`;
    }).join("") + `
    <div class="field"><label for="f-horizonte">Horizonte del proyecto (meses)</label>
      <input id="f-horizonte" type="number" data-k="horizonte_meses" value="${val("horizonte_meses")}" min="1" placeholder="Ej: 24"></div>`;
  }

  // paso 4: revisión
  const rows = [
    ["Nombre", d.nombre], ["Edad", d.edad], ["Ciudad", d.ciudad],
    ["Idioma", d.idioma], ["Zona horaria", d.timezone], ["Horas/semana", d.horas_semana],
    ["Tagline", d.tagline], ["Objetivo", d.objetivo],
    ["Rubro", d.rubro.join(", ")], ["Orientación", d.orientacion.join(", ")],
    ["Ofrecés", d.skills_ofrece.join(", ")], ["Buscás", d.skills_busca.join(", ")],
    ["Intereses", d.intereses.join(", ")], ["Horizonte", d.horizonte_meses ? d.horizonte_meses + " meses" : ""],
  ].filter(([, v]) => v);
  return `
    <p style="color:var(--muted)">Así se va a ver tu perfil. Si algo no te cierra, volvé atrás y ajustalo.</p>
    <ul class="review-list">
      ${rows.map(([k, v]) => `<li><span class="rk">${esc(k)}</span><span class="rv">${esc(v)}</span></li>`).join("")}
    </ul>`;
}

async function renderQuiz() {
  const q = state.quiz;
  try { await loadMeta(); } catch (err) { vista.innerHTML = apiErrorHTML(err); return; }

  vista.innerHTML = `<div class="vista-narrow" style="margin:0 auto">
    <div class="quiz-shell">
      <h1>Creá tu perfil</h1>
      <p>5 pasos rapiditos. Mientras más honesto, mejor el matching.</p>
      <ol class="stepper">
        ${QUIZ_STEPS.map((s, i) => `<li data-n="${i + 1}"
          class="${i < q.step ? "done" : i === q.step ? "current" : ""}">${s}</li>`).join("")}
      </ol>
      <div id="quiz-body">${quizStepHTML()}</div>
      <div class="quiz-nav">
        <button class="btn btn-ghost" id="quiz-back" type="button"${q.step === 0 ? " disabled" : ""}>Atrás</button>
        ${q.step < 4
          ? `<button class="btn btn-primary" id="quiz-next" type="button">Siguiente</button>`
          : `<button class="btn btn-primary" id="quiz-create" type="button">Crear mi perfil y ver mis matches</button>`}
      </div>
    </div>
  </div>`;

  wireQuizInputs();
  document.getElementById("quiz-back").addEventListener("click", () => {
    if (q.step > 0) { q.step--; renderQuiz(); }
  });
  const next = document.getElementById("quiz-next");
  if (next) next.addEventListener("click", () => {
    if (q.step === 0 && !q.data.nombre.trim()) {
      toast("Poné tu nombre para seguir");
      document.getElementById("f-nombre")?.focus();
      return;
    }
    q.step++; renderQuiz();
  });
  const create = document.getElementById("quiz-create");
  if (create) create.addEventListener("click", () => submitQuiz(create));
}

function wireQuizInputs() {
  const q = state.quiz, d = q.data;

  // inputs simples
  vista.querySelectorAll("[data-k]").forEach((el) => {
    el.addEventListener("input", () => { d[el.dataset.k] = el.value; });
    el.addEventListener("change", () => { d[el.dataset.k] = el.value; });
  });

  // sliders
  vista.querySelectorAll("[data-slider]").forEach((el) => {
    const key = el.dataset.slider;
    el.addEventListener("input", () => {
      const v = parseInt(el.value, 10);
      document.getElementById("sv-" + key).textContent = v;
      if (key === "inversion_dinero") d.inversion_dinero = v;
      else d.rasgos[key] = v;
    });
  });

  // chips multi-select
  vista.querySelectorAll("[data-group]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const g = btn.dataset.group, v = btn.dataset.v;
      const arr = d[g];
      const i = arr.indexOf(v);
      if (i >= 0) { arr.splice(i, 1); btn.classList.remove("active"); }
      else { arr.push(v); btn.classList.add("active"); }
    });
  });

  // agregar chip personalizado
  const addCustom = (group) => {
    const input = vista.querySelector(`[data-custom="${group}"]`);
    const v = (input.value || "").trim();
    if (!v) return;
    if (!d[group].includes(v)) d[group].push(v);
    const box = vista.querySelector(`[data-chips="${group}"]`);
    if (box && !box.querySelector(`[data-v="${CSS.escape(v)}"]`)) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip active" + (group === "intereses" ? " chip-gold" : "");
      b.dataset.group = group; b.dataset.v = v; b.textContent = v;
      b.addEventListener("click", () => {
        const arr = d[group], i = arr.indexOf(v);
        if (i >= 0) { arr.splice(i, 1); b.classList.remove("active"); }
        else { arr.push(v); b.classList.add("active"); }
      });
      box.appendChild(b);
    } else {
      box?.querySelector(`[data-v="${CSS.escape(v)}"]`)?.classList.add("active");
    }
    input.value = "";
  };
  vista.querySelectorAll("[data-add]").forEach((btn) => {
    btn.addEventListener("click", () => addCustom(btn.dataset.add));
  });
  vista.querySelectorAll("[data-custom]").forEach((input) => {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); addCustom(input.dataset.custom); }
    });
  });
}

function quizToPayload() {
  const d = state.quiz.data;
  const num = (v) => (v === "" || v == null ? null : Number(v));
  return {
    nombre: d.nombre.trim(),
    edad: num(d.edad),
    ciudad: d.ciudad.trim(),
    idioma: d.idioma,
    timezone: d.timezone,
    horas_semana: num(d.horas_semana),
    tagline: d.tagline.trim(),
    bio: d.bio.trim(),
    vision: d.vision.trim(),
    objetivo: d.objetivo,
    rubro: d.rubro,
    orientacion: d.orientacion,
    quien_busco: d.quien_busco.trim(),
    skills_ofrece: d.skills_ofrece,
    skills_busca: d.skills_busca,
    intereses: d.intereses,
    rasgos: {
      apetito_riesgo: d.rasgos.apetito_riesgo,
      estilo_decision: d.rasgos.estilo_decision,
      confianza: d.rasgos.confianza,
      energia: d.rasgos.energia,
      disciplina: d.rasgos.disciplina,
      creatividad: d.rasgos.creatividad,
    },
    inversion_dinero: d.inversion_dinero,
    horizonte_meses: num(d.horizonte_meses),
    objetivos_lista: d.objetivos_lista,
    proyectos_lista: d.proyectos_lista,
    disponibilidad: "Disponible",
  };
}

async function submitQuiz(btn) {
  const d = state.quiz.data;
  if (!d.nombre.trim()) { toast("Poné tu nombre para crear el perfil"); return; }
  btn.disabled = true;
  btn.textContent = "Creando tu perfil…";
  try {
    const created = await api("/api/profiles", {
      method: "POST",
      body: JSON.stringify(quizToPayload()),
    });
    localStorage.setItem(LS_KEY, String(created.id));
    state.myProfileId = String(created.id);
    state.myProfile = created;
    state.quiz = null;
    state.matches = [];
    state.matchesById = {};
    toast("¡Perfil creado! Estos son tus matches.");
    await renderOwnProfile();
    window.scrollTo(0, 0);
  } catch (err) {
    btn.disabled = false;
    btn.textContent = "Crear mi perfil y ver mis matches";
    toast("No se pudo crear el perfil. Intentá de nuevo.");
  }
}

/* ----- mi perfil + mis matches ----- */
function matchRowHTML(m, i) {
  const p = m.profile || {};
  const pct = Math.round((m.total || 0) * 100);
  return `<div class="match-row" data-mid="${esc(p.id)}">
    <button class="match-row-head" type="button" aria-expanded="false">
      ${ring(pct, 52, { color: m.pasa_filtros ? "var(--coral)" : "var(--gray-dot)" })}
      <span class="match-row-info"><strong>#${i + 1} · ${esc(p.nombre)}</strong>
        <span>${esc(p.edad)} · ${esc(p.ciudad)}${m.pasa_filtros ? "" : " · descartado por filtros duros"}</span></span>
      <span class="match-row-score${m.pasa_filtros ? "" : " dim"}">${pct}%</span>
      <span class="match-expand" aria-hidden="true">▾</span>
    </button>
    <div class="match-row-detail">
      ${compatHTML(m)}
      <div class="match-row-actions">
        <button class="btn btn-ghost btn-sm" type="button" data-ver="${esc(p.id)}">Ver perfil</button>
      </div>
    </div>
  </div>`;
}

async function renderOwnProfile() {
  const me = state.myProfile || await loadMyProfile();
  let matchesHTML = `<div class="spinner" role="status" aria-label="Calculando matches"></div>`;
  vista.innerHTML = `<div class="vista-narrow" style="margin:0 auto">
    <div class="own-profile">
      <span class="conn-avatar" style="background:${gradientFor(me.id)};width:72px;height:72px;font-size:1.8rem" aria-hidden="true">${esc(initials(me.nombre))}</span>
      <div class="who">
        <h1>${esc(me.nombre)}</h1>
        <p class="meta">${esc(me.edad)} · ${esc(me.ciudad)}${me.idioma ? " · " + esc(me.idioma) : ""}</p>
        ${me.tagline ? `<p class="tagline">“${esc(me.tagline)}”</p>` : ""}
      </div>
      <button class="btn btn-ghost" id="btn-ver-perfil" type="button">Ver mi perfil completo</button>
    </div>
    <div class="matches-head"><h2>Mis matches</h2><span style="color:var(--muted);font-size:.9rem">Ordenados por compatibilidad</span></div>
    <div id="matches-list">${matchesHTML}</div>
    <div class="danger-zone">
      <button class="btn-danger" id="btn-borrar" type="button">Borrar mi perfil local</button>
    </div>
  </div>`;

  document.getElementById("btn-ver-perfil").addEventListener("click", () => openModal(me.id));
  document.getElementById("btn-borrar").addEventListener("click", () => {
    if (confirm("¿Borrar tu perfil de este dispositivo? Vas a tener que crearlo de nuevo para ver matches.")) {
      localStorage.removeItem(LS_KEY);
      state.myProfileId = null;
      state.myProfile = null;
      state.matches = [];
      state.matchesById = {};
      state.connections = [];
      state.quiz = null;
      toast("Perfil local borrado");
      renderPerfil();
    }
  });

  try {
    const matches = await loadMatches();
    const sorted = [...matches].sort((a, b) =>
      (b.pasa_filtros - a.pasa_filtros) || ((b.total || 0) - (a.total || 0)));
    const list = document.getElementById("matches-list");
    if (!sorted.length) {
      list.innerHTML = `<div class="empty-state"><h2>Todavía no hay matches</h2>
        <p>Cuando haya más personas en Zipzi, acá vas a ver tu ranking de compatibilidad.</p></div>`;
      return;
    }
    list.innerHTML = sorted.map(matchRowHTML).join("");
    list.querySelectorAll(".match-row").forEach((row) => {
      const head = row.querySelector(".match-row-head");
      head.addEventListener("click", () => {
        const open = row.classList.toggle("open");
        head.setAttribute("aria-expanded", String(open));
      });
    });
    list.querySelectorAll("[data-ver]").forEach((btn) => {
      btn.addEventListener("click", (e) => { e.stopPropagation(); openModal(btn.dataset.ver); });
    });
  } catch (err) {
    document.getElementById("matches-list").innerHTML = apiErrorHTML(err);
  }
}

/* ---------- init ---------- */
if (!location.hash) location.hash = "#/descubrir";
render();
