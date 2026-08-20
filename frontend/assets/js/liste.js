// Liste des réclamations avec filtres avancés.
if (!requireAuth()) throw new Error("redirect");
document.getElementById("app").innerHTML = renderLayout("liste", "Toutes les réclamations");
brancherLogout();
const content = document.getElementById("content");

const STATUTS = ["NOUVEAU", "QUALIF", "AFFECTE", "EN_COURS", "ATT_CLIENT", "ALERTE",
                 "ESCALADE", "VALIDATION", "DECISION", "CLOTURE", "REJETE", "REOUVRE"];
const PRIORITES = ["STANDARD", "URGENT", "CRITIQUE"];
const CATEGORIES = ["FINANCIERE", "CONTRACTUELLE", "SERVICE", "FRAUDE"];
const CANAUX = ["EMAIL", "AGENCE", "TELEPHONE", "WEB", "WHATSAPP", "COURRIER"];

let agents = [];
const params = new URLSearchParams(location.search);
const filtres = {
  statut:     params.get("statut") || "",
  priorite:   params.get("priorite") || "",
  categorie:  params.get("categorie") || "",
  canal:      params.get("canal") || "",
  id_equipe_affectee: params.get("id_equipe_affectee") || "",
  date_debut: params.get("date_debut") || "",
  date_fin:   params.get("date_fin") || "",
  q:          params.get("q") || "",
  en_alerte:  params.get("en_alerte") === "true",
  skip:       parseInt(params.get("skip") || "0", 10),
  limit:      parseInt(params.get("limit") || "25", 10),
};
let equipes = [];
let total = 0;

async function charger() {
  content.innerHTML = `<div class="card">Chargement…</div>`;
  try {
    [equipes, agents] = await Promise.all([
      api.get("/api/equipes"),
      auth.isAdmin() ? api.get("/api/agents") : Promise.resolve([]),
    ]);
    const qs = new URLSearchParams();
    Object.entries(filtres).forEach(([k, v]) => {
      if (v === "" || v === false || v === 0) return;
      qs.set(k, v);
    });
    qs.set("skip", String(filtres.skip));
    qs.set("limit", String(filtres.limit));

    const res = await fetch("/api/reclamations?" + qs, {
      headers: { "Authorization": "Bearer " + auth.token() },
    });
    if (!res.ok) {
      if (res.status === 401) { auth.logout(); return; }
      const j = await res.json().catch(() => ({}));
      throw new Error(j.detail || `Erreur ${res.status}`);
    }
    total = parseInt(res.headers.get("X-Total-Count") || "0", 10);
    const list = await res.json();
    content.innerHTML = render(list);
    brancherFiltres();
  } catch (err) {
    content.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

function render(list) {
  const filtreUi = `
    <div class="card">
      <div class="card-head"><span class="card-title">Filtres</span></div>
      <div class="form-grid" style="grid-template-columns:repeat(4,1fr);gap:10px">
        <div>
          <label>Recherche</label>
          <input id="f_q" value="${esc(filtres.q)}" placeholder="code, mot-clé, sous-catégorie…">
        </div>
        <div>
          <label>Statut</label>
          <select id="f_statut">
            <option value="">Tous</option>
            ${STATUTS.map(s => `<option ${filtres.statut === s ? "selected" : ""}>${s}</option>`).join("")}
          </select>
        </div>
        <div>
          <label>Priorité</label>
          <select id="f_priorite">
            <option value="">Toutes</option>
            ${PRIORITES.map(p => `<option ${filtres.priorite === p ? "selected" : ""}>${p}</option>`).join("")}
          </select>
        </div>
        <div>
          <label>Catégorie</label>
          <select id="f_categorie">
            <option value="">Toutes</option>
            ${CATEGORIES.map(c => `<option ${filtres.categorie === c ? "selected" : ""}>${c}</option>`).join("")}
          </select>
        </div>
        <div>
          <label>Canal</label>
          <select id="f_canal">
            <option value="">Tous</option>
            ${CANAUX.map(c => `<option ${filtres.canal === c ? "selected" : ""}>${c}</option>`).join("")}
          </select>
        </div>
        <div>
          <label>Équipe affectée</label>
          <select id="f_equipe">
            <option value="">Toutes</option>
            ${equipes.map(e => `<option value="${e.id}" ${String(filtres.id_equipe_affectee) === String(e.id) ? "selected" : ""}>${e.libelle}</option>`).join("")}
          </select>
        </div>
        <div>
          <label>Du (date de réception)</label>
          <input type="date" id="f_date_debut" value="${(filtres.date_debut || "").slice(0,10)}">
        </div>
        <div>
          <label>Au</label>
          <input type="date" id="f_date_fin" value="${(filtres.date_fin || "").slice(0,10)}">
        </div>
        <div class="full" style="display:flex;gap:10px;align-items:center;justify-content:space-between">
          <label style="margin:0">
            <input type="checkbox" id="f_alerte" ${filtres.en_alerte ? "checked" : ""}>
            En alerte SLA uniquement
          </label>
          <div style="display:flex;gap:8px">
            <button class="btn" id="f_reset">Réinitialiser</button>
            <button class="btn btn-primary" id="f_appliquer">Appliquer</button>
          </div>
        </div>
      </div>
    </div>`;

  const pageStart = total === 0 ? 0 : filtres.skip + 1;
  const pageEnd = Math.min(filtres.skip + filtres.limit, total);
  const totalPages = Math.max(1, Math.ceil(total / filtres.limit));
  const pageCourante = Math.floor(filtres.skip / filtres.limit) + 1;

  const compteur = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;font-size:13px;color:var(--text-soft)">
      <span><strong style="color:var(--text)">${total}</strong> réclamation${total > 1 ? "s" : ""} au total — affichage ${pageStart}–${pageEnd}</span>
      <div style="display:flex;align-items:center;gap:6px">
        <span style="font-size:12px">Lignes par page</span>
        <select id="f_limit" style="padding:4px 6px;width:70px">
          ${[10, 25, 50, 100, 200].map(n =>
            `<option value="${n}" ${filtres.limit === n ? "selected" : ""}>${n}</option>`).join("")}
        </select>
        <button class="btn" id="page_prev" ${filtres.skip <= 0 ? "disabled" : ""} style="padding:4px 10px">‹ Préc.</button>
        <span style="font-size:12px;font-variant-numeric:tabular-nums">Page ${pageCourante} / ${totalPages}</span>
        <button class="btn" id="page_next" ${pageEnd >= total ? "disabled" : ""} style="padding:4px 10px">Suiv. ›</button>
      </div>
    </div>`;

  if (list.length === 0) {
    return filtreUi + compteur + `<div class="card empty">Aucune réclamation ne correspond aux filtres.</div>`;
  }

  const bulkBar = auth.isAdmin() ? `
    <div id="bulk_bar" style="display:none;position:sticky;bottom:16px;background:var(--brand);color:#fff;border-radius:10px;padding:12px 18px;display:none;align-items:center;gap:12px;box-shadow:0 4px 16px rgba(0,0,0,.18);z-index:100;margin-top:10px">
      <span id="bulk_count" style="font-weight:600"></span> sélectionné(s)
      <select id="bulk_agent" style="padding:5px 8px;border-radius:6px;border:none;font-size:13px">
        ${agents.map(a => `<option value="${a.id}">${a.prenom} ${a.nom} — ${a.role}</option>`).join("")}
      </select>
      <button class="btn" id="bulk_affecter" style="background:#fff;color:var(--brand);font-weight:600">Réassigner</button>
      <button class="btn" id="bulk_cancel" style="background:rgba(255,255,255,.2);color:#fff">Annuler</button>
    </div>` : "";

  const table = `<div class="card">
    <table class="tbl">
      <thead><tr>
        ${auth.isAdmin() ? `<th style="width:32px"><input type="checkbox" id="chk_all" title="Tout sélectionner"></th>` : ""}
        <th>Dossier</th><th>Client</th><th>Catégorie</th><th>Canal</th><th>Priorité</th>
        <th>Équipe</th><th>SLA</th><th>Statut</th><th>Reçue le</th>
      </tr></thead>
      <tbody>${list.map(r => `
        <tr onclick="location='/detail.html?code=${r.code}'" data-code="${r.code}">
          ${auth.isAdmin() ? `<td onclick="event.stopPropagation()"><input type="checkbox" class="chk_row" value="${r.code}"></td>` : ""}
          <td><span class="code">${r.code}</span></td>
          <td>${esc(r.client.prenom)} ${esc(r.client.nom)}</td>
          <td>${esc(r.sous_categorie || r.categorie)}</td>
          <td>${r.canal}</td>
          <td>${pillPriorite(r.priorite)}</td>
          <td style="font-size:12px;color:var(--text-soft)">${r.equipe_affectee ? esc(r.equipe_affectee.libelle) : "—"}</td>
          <td>${pillSla(r.sla_statut, r.sla_pourcentage)}</td>
          <td>${pillStatut(r.statut)}</td>
          <td style="font-size:12px;color:var(--text-soft)">${formaterDate(r.date_reception)}</td>
        </tr>`).join("")}</tbody>
    </table>
  </div>${bulkBar}`;

  return filtreUi + compteur + table;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;" }[c]));
}

function brancherFiltres() {
  const construireQs = (overrides = {}) => {
    const qs = new URLSearchParams();
    const v = (id) => document.getElementById(id).value;
    if (v("f_q"))          qs.set("q", v("f_q"));
    if (v("f_statut"))     qs.set("statut", v("f_statut"));
    if (v("f_priorite"))   qs.set("priorite", v("f_priorite"));
    if (v("f_categorie"))  qs.set("categorie", v("f_categorie"));
    if (v("f_canal"))      qs.set("canal", v("f_canal"));
    if (v("f_equipe"))     qs.set("id_equipe_affectee", v("f_equipe"));
    const d1 = v("f_date_debut");
    const d2 = v("f_date_fin");
    if (d1) qs.set("date_debut", d1 + "T00:00:00");
    if (d2) qs.set("date_fin",   d2 + "T23:59:59");
    if (document.getElementById("f_alerte").checked) qs.set("en_alerte", "true");
    Object.entries(overrides).forEach(([k, v]) => { if (v !== null) qs.set(k, v); });
    return qs;
  };

  document.getElementById("f_appliquer").onclick = () => {
    location.search = construireQs({ skip: 0, limit: filtres.limit }).toString();
  };
  document.getElementById("f_reset").onclick = () => { location.search = ""; };

  const limitSel = document.getElementById("f_limit");
  if (limitSel) limitSel.onchange = () => {
    const qs = new URLSearchParams(location.search);
    qs.set("limit", limitSel.value);
    qs.set("skip", "0");
    location.search = qs.toString();
  };
  const prev = document.getElementById("page_prev");
  const next = document.getElementById("page_next");
  if (prev) prev.onclick = () => {
    const qs = new URLSearchParams(location.search);
    qs.set("skip", Math.max(0, filtres.skip - filtres.limit));
    qs.set("limit", filtres.limit);
    location.search = qs.toString();
  };
  if (next) next.onclick = () => {
    const qs = new URLSearchParams(location.search);
    qs.set("skip", filtres.skip + filtres.limit);
    qs.set("limit", filtres.limit);
    location.search = qs.toString();
  };

  // Sélection en masse (admin uniquement)
  if (!auth.isAdmin()) return;
  const chkAll = document.getElementById("chk_all");
  const bulkBar = document.getElementById("bulk_bar");
  if (!chkAll || !bulkBar) return;

  function majBulkBar() {
    const sel = document.querySelectorAll(".chk_row:checked");
    if (sel.length > 0) {
      bulkBar.style.display = "flex";
      document.getElementById("bulk_count").textContent = sel.length;
    } else {
      bulkBar.style.display = "none";
    }
  }

  chkAll.onchange = () => {
    document.querySelectorAll(".chk_row").forEach(c => { c.checked = chkAll.checked; });
    majBulkBar();
  };
  document.querySelectorAll(".chk_row").forEach(c => c.onchange = majBulkBar);

  document.getElementById("bulk_cancel").onclick = () => {
    document.querySelectorAll(".chk_row").forEach(c => { c.checked = false; });
    chkAll.checked = false;
    bulkBar.style.display = "none";
  };

  document.getElementById("bulk_affecter").onclick = async () => {
    const codes = [...document.querySelectorAll(".chk_row:checked")].map(c => c.value);
    const id_agent = parseInt(document.getElementById("bulk_agent").value, 10);
    if (!codes.length) return;
    try {
      const res = await api.patch("/api/reclamations/bulk/affecter", { codes, id_agent });
      alert(`${res.reassignes} dossier(s) réassigné(s) avec succès.`);
      charger();
    } catch (e) {
      alert("Erreur : " + e.message);
    }
  };
}

charger();
