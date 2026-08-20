// Wrapper d'appels API + gestion du token JWT.
const API_BASE = window.location.origin;

const auth = {
  token:  () => localStorage.getItem("rp_token"),
  user:   () => { try { return JSON.parse(localStorage.getItem("rp_user") || "null"); } catch { return null; } },
  isAdmin:() => (auth.user() || {}).role === "ADMIN",
  logout: () => { localStorage.removeItem("rp_token"); localStorage.removeItem("rp_user"); location.href = "/login.html"; },
};

async function apiRequest(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = auth.token();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const opts = { method, headers };
  if (body !== undefined) opts.body = JSON.stringify(body);

  const res = await fetch(API_BASE + path, opts);

  if (res.status === 401 && !path.startsWith("/api/auth/login")) {
    auth.logout();
    return;
  }

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const message = (data && data.detail) ? data.detail : `Erreur ${res.status}`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return data;
}

const api = {
  get:    (p)    => apiRequest("GET",    p),
  post:   (p, b) => apiRequest("POST",   p, b),
  patch:  (p, b) => apiRequest("PATCH",  p, b),
  del:    (p)    => apiRequest("DELETE", p),
};

// Sur toute page protégée, exige un token au chargement.
function requireAuth() {
  if (!auth.token()) {
    location.href = "/login.html";
    return false;
  }
  return true;
}

function formaterDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}

function pillStatut(statut) {
  const map = {
    NOUVEAU: "pill-blue", QUALIF: "pill-blue", AFFECTE: "pill-blue",
    EN_COURS: "pill-orange", ATT_CLIENT: "pill-orange",
    ALERTE: "pill-red", ESCALADE: "pill-red",
    VALIDATION: "pill-blue", DECISION: "pill-blue",
    CLOTURE: "pill-green", REJETE: "pill-gray", REOUVRE: "pill-orange",
  };
  return `<span class="pill ${map[statut] || "pill-gray"}">${statut}</span>`;
}

function pillPriorite(p) {
  const map = { CRITIQUE: "pill-red", URGENT: "pill-orange", STANDARD: "pill-gray" };
  return `<span class="pill ${map[p] || "pill-gray"}">${p}</span>`;
}

function pillSla(slaStatut, pct) {
  if (slaStatut === "ECHU")    return `<span class="pill pill-red">Échu</span>`;
  if (slaStatut === "ALERTE")  return `<span class="pill pill-orange">${pct}%</span>`;
  if (slaStatut === "TERMINE") return `<span class="pill pill-gray">—</span>`;
  return `<span class="pill pill-green">${pct}%</span>`;
}

function slaBarHtml(slaStatut, pct) {
  const cls = slaStatut === "ECHU" ? "sla-crit" :
              slaStatut === "ALERTE" ? "sla-warn" :
              slaStatut === "TERMINE" ? "" : "sla-ok";
  const largeur = Math.min(100, Math.max(2, pct || 0));
  return `<div class="sla-bar"><div class="sla-fill ${cls}" style="width:${largeur}%"></div></div>`;
}
