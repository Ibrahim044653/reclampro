// Ma file — espace personnel de chaque utilisateur connecté.
if (!requireAuth()) throw new Error("redirect");
document.getElementById("app").innerHTML = renderLayout("ma-file", "Ma file de traitement");
brancherLogout();
const content = document.getElementById("content");

const groupe = new URLSearchParams(location.search).get("statut_groupe") || "a_traiter";

async function init() {
  content.innerHTML = `<div class="card">Chargement de votre file…</div>`;
  try {
    const [bilan, dossiers] = await Promise.all([
      api.get("/api/reclamations/mon-bilan"),
      api.get(`/api/reclamations/mes${groupe !== "tous" ? `?statut_groupe=${groupe}` : ""}`),
    ]);
    content.innerHTML = render(bilan, dossiers);
  } catch (err) {
    content.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

function render(bilan, dossiers) {
  const onglets = [
    { id: "a_traiter", label: "À traiter",  v: bilan.a_traiter, c: "var(--brand)" },
    { id: "en_cours",  label: "En cours",   v: bilan.en_cours,  c: "var(--warn)" },
    { id: "traites",   label: "Traités",    v: bilan.traites,   c: "var(--ok)" },
    { id: "tous",      label: "Tous",       v: bilan.total,     c: "var(--text)" },
  ];

  const bilanCard = `
    <div class="card">
      <div class="card-head">
        <span class="card-title">Mon bilan — ${esc(bilan.agent.nom_complet)}
          ${bilan.agent.equipe ? ` <span class="pill pill-blue">${esc(bilan.agent.equipe)}</span>` : ""}
        </span>
      </div>
      <div class="kpi-row" style="grid-template-columns:repeat(5,1fr)">
        <div class="mini-kpi"><div class="v" style="color:var(--brand)">${bilan.a_traiter}</div><div class="l">À traiter</div></div>
        <div class="mini-kpi"><div class="v" style="color:var(--warn)">${bilan.en_cours}</div><div class="l">En cours</div></div>
        <div class="mini-kpi"><div class="v" style="color:var(--ok)">${bilan.traites}</div><div class="l">Traités</div></div>
        <div class="mini-kpi"><div class="v" style="color:${bilan.en_alerte_sla > 0 ? "var(--crit)" : "var(--text)"}">${bilan.en_alerte_sla}</div><div class="l">Alerte SLA</div></div>
        <div class="mini-kpi"><div class="v">${bilan.total}</div><div class="l">Total dossiers</div></div>
      </div>
    </div>`;

  const ongletsHtml = `
    <div class="card" style="padding:8px 14px">
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        ${onglets.map(o => `
          <a href="?statut_groupe=${o.id}"
             class="btn ${o.id === groupe ? "btn-primary" : ""}"
             style="padding:6px 12px;font-weight:${o.id === groupe ? "600" : "400"}">
            ${o.label} <span style="opacity:0.7;margin-left:4px">(${o.v})</span>
          </a>`).join("")}
      </div>
    </div>`;

  const liste = dossiers.length === 0
    ? `<div class="card empty">Aucun dossier dans cette catégorie.</div>`
    : `<div class="card">
        <table class="tbl">
          <thead><tr>
            <th>Dossier</th><th>Client</th><th>Catégorie</th><th>Priorité</th>
            <th>SLA</th><th>Statut</th><th>Échéance</th>
          </tr></thead>
          <tbody>${dossiers.map(r => `
            <tr onclick="location='/detail.html?code=${r.code}'">
              <td><span class="code">${r.code}</span></td>
              <td>${esc(r.client.prenom)} ${esc(r.client.nom)}</td>
              <td>${esc(r.sous_categorie || r.categorie)}</td>
              <td>${pillPriorite(r.priorite)}</td>
              <td>${pillSla(r.sla_statut, r.sla_pourcentage)}</td>
              <td>${pillStatut(r.statut)}</td>
              <td style="font-size:12px;color:var(--text-soft)">${formaterDate(r.date_echeance_sla)}</td>
            </tr>`).join("")}</tbody>
        </table>
      </div>`;

  return bilanCard + ongletsHtml + liste;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;" }[c]));
}

init();
