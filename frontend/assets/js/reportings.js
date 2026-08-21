// Reportings de pilotage — admin seulement.
if (!requireAuth()) throw new Error("redirect");
if (!auth.isAdmin()) { location.href = "/"; throw new Error("forbidden"); }

document.getElementById("app").innerHTML = renderLayout("reportings", "Reportings — Pilotage de l'activité");
brancherLogout();
const content = document.getElementById("content");

const params = new URLSearchParams(location.search);
const filtres = {
  periode: params.get("periode") || "mois",
  dim:     params.get("dim") || "categorie",
  granularite: params.get("granularite") || "mois",
};

async function init() {
  content.innerHTML = renderShell();
  brancherFiltres();
  await rafraichir();
}

function renderShell() {
  return `
    <div class="card">
      <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:end">
        <div>
          <label>Période d'analyse</label>
          <select id="f_periode">
            ${["semaine", "mois", "trimestre", "annee"].map(p =>
              `<option value="${p}" ${filtres.periode === p ? "selected" : ""}>${p.charAt(0).toUpperCase()+p.slice(1)} en cours</option>`).join("")}
          </select>
        </div>
        <div>
          <label>Dimension d'analyse</label>
          <select id="f_dim">
            ${[
              ["categorie","Par catégorie"],
              ["sous_categorie","Par sous-catégorie"],
              ["priorite","Par priorité"],
              ["canal","Par canal"],
              ["equipe","Par équipe"],
              ["statut","Par statut"],
              ["agent","Par agent"],
            ].map(([v,l]) => `<option value="${v}" ${filtres.dim === v ? "selected" : ""}>${l}</option>`).join("")}
          </select>
        </div>
        <div>
          <label>Granularité (série temporelle)</label>
          <select id="f_granularite">
            ${[["jour","Jour"],["semaine","Semaine"],["mois","Mois"],["annee","Année"]]
              .map(([v,l]) => `<option value="${v}" ${filtres.granularite === v ? "selected" : ""}>${l}</option>`).join("")}
          </select>
        </div>
        <button class="btn btn-primary" id="f_appliquer">Appliquer</button>
        <div style="margin-left:auto;display:flex;gap:8px">
          <button class="btn" id="btn_export_csv" title="Exporter la période en CSV">CSV</button>
          <button class="btn" id="btn_export_xlsx" title="Exporter la période en Excel">Excel</button>
        </div>
      </div>
    </div>
    <div id="resultats"></div>
  `;
}

function brancherFiltres() {
  document.getElementById("f_appliquer").onclick = () => {
    const qs = new URLSearchParams({
      periode: document.getElementById("f_periode").value,
      dim: document.getElementById("f_dim").value,
      granularite: document.getElementById("f_granularite").value,
    });
    location.search = qs.toString();
  };

  async function telecharger(format) {
    const periode = document.getElementById("f_periode").value;
    const url = `/api/exports/registre.${format}?token=${auth.token()}&periode=${periode}`;
    try {
      const res = await fetch(url, { headers: { "Authorization": "Bearer " + auth.token() } });
      if (!res.ok) throw new Error("Export impossible (" + res.status + ")");
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `reporting_${periode}_${new Date().toISOString().slice(0,10)}.${format}`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) { alert(e.message); }
  }

  document.getElementById("btn_export_csv").onclick  = () => telecharger("csv");
  document.getElementById("btn_export_xlsx").onclick = () => telecharger("xlsx");
}

async function rafraichir() {
  const res = document.getElementById("resultats");
  res.innerHTML = `<div class="card">Calcul des indicateurs…</div>`;
  try {
    const [synthese, parDim, serie, conformite, parEquipe, parAgent] = await Promise.all([
      api.get(`/api/reports/synthese?periode=${filtres.periode}`),
      api.get(`/api/reports/par-dimension?dim=${filtres.dim}&periode=${filtres.periode}`),
      api.get(`/api/reports/serie-temporelle?granularite=${filtres.granularite}&points=12`),
      api.get(`/api/reports/conformite-sla?dim=priorite&periode=${filtres.periode}`),
      api.get(`/api/reports/par-equipe?periode=${filtres.periode}`),
      api.get(`/api/reports/par-agent?periode=${filtres.periode}`),
    ]);
    res.innerHTML = render(synthese, parDim, serie, conformite, parEquipe, parAgent);
  } catch (err) {
    res.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

function render(synth, parDim, serie, conf, parEquipe, parAgent) {
  const periodeLabel = `${formaterDate(synth.date_debut)} → ${formaterDate(synth.date_fin)}`;

  const kpis = `
    <div class="card">
      <div class="card-head">
        <span class="card-title">Synthèse de la période</span>
        <span style="font-size:12px;color:var(--text-soft)">${periodeLabel}</span>
      </div>
      <div class="kpi-row" style="grid-template-columns:repeat(5,1fr)">
        <div class="mini-kpi"><div class="v">${synth.total_recues}</div><div class="l">Reçues</div></div>
        <div class="mini-kpi"><div class="v">${synth.total_cloturees}</div><div class="l">Clôturées</div></div>
        <div class="mini-kpi"><div class="v">${synth.total_en_cours}</div><div class="l">En cours</div></div>
        <div class="mini-kpi"><div class="v">${synth.delai_moyen_traitement_heures}h</div><div class="l">Délai moyen</div></div>
        <div class="mini-kpi"><div class="v" style="color:${synth.taux_conformite_sla >= 80 ? "#1D9E75" : "#E24B4A"}">${synth.taux_conformite_sla}%</div><div class="l">Conformité SLA</div></div>
      </div>
    </div>`;

  const serieCard = (() => {
    const labels = serie.points.map(p => p.label);
    const series = [
      { label: "Reçues",    valeurs: serie.points.map(p => p.recues),    couleur: "#185FA5" },
      { label: "Clôturées", valeurs: serie.points.map(p => p.cloturees), couleur: "#1D9E75" },
    ];
    return `
      <div class="card">
        <div class="card-head">
          <span class="card-title">Série temporelle — ${filtres.granularite}</span>
          <div style="display:flex;gap:14px;font-size:11px;color:var(--text-soft)">
            <span><span style="color:#185FA5">●</span> Reçues</span>
            <span><span style="color:#1D9E75">●</span> Clôturées</span>
          </div>
        </div>
        ${lineChartSvg(labels, series, { width: 800, height: 220 })}
      </div>`;
  })();

  const dimCard = (() => {
    const top = parDim.items.slice(0, 12);
    if (top.length === 0) return `<div class="card empty">Aucune donnée pour cette période.</div>`;
    return `
      <div class="card">
        <div class="card-head"><span class="card-title">Analyse ${dimLabel(parDim.dimension)}</span></div>
        <table class="tbl">
          <thead><tr>
            <th>${dimLabel(parDim.dimension)}</th><th>Reçues</th><th>Clôturées</th>
            <th>Taux clôture</th><th>Conformité SLA</th>
          </tr></thead>
          <tbody>${top.map(it => `
            <tr>
              <td><strong>${esc(it.modalite)}</strong></td>
              <td>${it.recues}</td>
              <td>${it.cloturees}</td>
              <td>${barreInline(it.taux_cloture_pct, "#1D9E75")}</td>
              <td>${barreInline(it.taux_conformite_sla_pct, conformiteColor(it.taux_conformite_sla_pct))}</td>
            </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  })();

  const confCard = (() => {
    if (conf.items.length === 0) return "";
    return `
      <div class="card">
        <div class="card-head">
          <span class="card-title">Contrôle conformité SLA par priorité</span>
          <span style="font-size:11px;color:var(--text-soft)">Détail OK / Alerte / Échu</span>
        </div>
        <table class="tbl">
          <thead><tr>
            <th>Priorité</th><th>Total</th>
            <th style="color:#1D9E75">OK</th>
            <th style="color:#BA7517">Alerte</th>
            <th style="color:#E24B4A">Échu</th>
            <th>Conformité</th>
          </tr></thead>
          <tbody>${conf.items.map(it => `
            <tr>
              <td><strong>${esc(it.modalite)}</strong></td>
              <td>${it.total}</td>
              <td>${it.ok}</td>
              <td>${it.alerte}</td>
              <td>${it.echu}</td>
              <td>${it.conformite_pct == null
                ? `<span style="color:var(--text-mute)">—</span>`
                : barreInline(it.conformite_pct, conformiteColor(it.conformite_pct))}</td>
            </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  })();

  const motifsCard = synth.repartition_motif_cloture.length === 0 ? "" : `
    <div class="card">
      <div class="card-head"><span class="card-title">Motifs de clôture (période)</span></div>
      ${synth.repartition_motif_cloture.map((m, i) => `
        <div class="hbar-row">
          <div class="hbar-lbl">${esc(m.label)}</div>
          <div class="hbar-track"><div class="hbar-fill" style="width:${(m.valeur / synth.total_cloturees * 100) || 0}%;background:${couleurPour(i)}"></div></div>
          <div class="hbar-val">${m.valeur}</div>
        </div>`).join("")}
    </div>`;

  const equipeCard = cardParEquipe(parEquipe);
  const agentCard = cardParAgent(parAgent);

  return kpis + serieCard + equipeCard + agentCard + dimCard + confCard + motifsCard;
}

function cardParEquipe(data) {
  if (!data.items.length) return "";
  return `
    <div class="card">
      <div class="card-head">
        <span class="card-title">Volume par équipe / cellule</span>
        <span style="font-size:11px;color:var(--text-soft)">Cliquer une ligne pour voir les dossiers</span>
      </div>
      <table class="tbl">
        <thead><tr>
          <th>Équipe</th><th>Membres</th><th>Total</th>
          <th>À traiter</th><th>En cours</th><th>Traités</th>
          <th>Alerte SLA</th><th>Échus</th>
          <th>Taux clôture</th><th>Délai moyen</th>
        </tr></thead>
        <tbody>${data.items.map(it => `
          <tr ${it.id_equipe ? `onclick="location='/reclamations.html?id_equipe_affectee=${it.id_equipe}'" style="cursor:pointer"` : ""}>
            <td><strong>${esc(it.libelle)}</strong>${it.code ? ` <span class="pill pill-gray" style="font-size:10px">${it.code}</span>` : ""}</td>
            <td style="color:var(--text-soft)">${it.nb_membres_actifs}</td>
            <td><strong>${it.total}</strong></td>
            <td><span class="pill pill-blue">${it.a_traiter}</span></td>
            <td><span class="pill pill-orange">${it.en_cours}</span></td>
            <td><span class="pill pill-green">${it.traites}</span></td>
            <td>${it.en_alerte_sla > 0 ? `<span class="pill pill-orange">${it.en_alerte_sla}</span>` : "—"}</td>
            <td>${it.sla_echus > 0 ? `<span class="pill pill-red">${it.sla_echus}</span>` : "—"}</td>
            <td>${barreInline(it.taux_cloture_pct, "#1D9E75")}</td>
            <td style="color:var(--text-soft)">${it.delai_moyen_heures}h</td>
          </tr>`).join("")}</tbody>
      </table>
    </div>`;
}

function cardParAgent(data) {
  const items = data.items.filter(it => it.total > 0 || it.id_agent !== null);
  if (!items.length) return "";
  return `
    <div class="card">
      <div class="card-head">
        <span class="card-title">Performance par agent</span>
        <span style="font-size:11px;color:var(--text-soft)">Cliquer un agent pour voir ses dossiers</span>
      </div>
      <table class="tbl">
        <thead><tr>
          <th>Agent</th><th>Rôle</th><th>Équipe</th>
          <th>Total</th><th>À traiter</th><th>En cours</th><th>Traités</th>
          <th>Alerte SLA</th><th>Échus</th><th>Délai moyen</th>
        </tr></thead>
        <tbody>${items.map(it => `
          <tr ${it.id_agent ? `onclick="location='/reclamations.html?id_agent_affecte=${it.id_agent}'" style="cursor:pointer"` : ""}>
            <td>
              <strong>${esc(it.nom_complet)}</strong>
              ${it.username ? `<div style="font-size:11px;color:var(--text-soft)">@${esc(it.username)}</div>` : ""}
            </td>
            <td>${it.role ? `<span class="pill pill-gray" style="font-size:10px">${it.role}</span>` : "—"}</td>
            <td style="color:var(--text-soft);font-size:12px">${it.equipe || "—"}</td>
            <td><strong>${it.total}</strong></td>
            <td><span class="pill pill-blue">${it.a_traiter}</span></td>
            <td><span class="pill pill-orange">${it.en_cours}</span></td>
            <td><span class="pill pill-green">${it.traites}</span></td>
            <td>${it.en_alerte_sla > 0 ? `<span class="pill pill-orange">${it.en_alerte_sla}</span>` : "—"}</td>
            <td>${it.sla_echus > 0 ? `<span class="pill pill-red">${it.sla_echus}</span>` : "—"}</td>
            <td style="color:var(--text-soft)">${it.delai_moyen_heures}h</td>
          </tr>`).join("")}</tbody>
      </table>
    </div>`;
}

function dimLabel(d) {
  return ({ categorie:"Catégorie", sous_categorie:"Sous-catégorie", priorite:"Priorité",
            canal:"Canal", equipe:"Équipe", statut:"Statut", agent:"Agent" })[d] || d;
}

function barreInline(pct, couleur) {
  return `
    <div style="display:flex;align-items:center;gap:8px">
      <div style="flex:1;height:8px;background:var(--bg);border-radius:4px;overflow:hidden;max-width:140px">
        <div style="height:100%;width:${pct}%;background:${couleur};border-radius:4px"></div>
      </div>
      <span style="font-variant-numeric:tabular-nums;color:var(--text-soft);font-size:12px;min-width:42px;text-align:right">${pct}%</span>
    </div>`;
}

function conformiteColor(pct) {
  if (pct >= 80) return "#1D9E75";
  if (pct >= 50) return "#BA7517";
  return "#E24B4A";
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;" }[c]));
}

init();
