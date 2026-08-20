// Tableau de bord — mise en page inspirée de docs/Dashboard.png.
if (!requireAuth()) throw new Error("redirect");
document.getElementById("app").innerHTML = renderLayout("dashboard", "Tableau de bord — Supervision");
brancherLogout();

const content = document.getElementById("content");

const COULEURS_SLA = { "Conforme": "#1D9E75", "En alerte": "#BA7517", "Échu": "#E24B4A", "Terminé": "#888780" };
const COULEURS_PRIO = { "CRITIQUE": "#E24B4A", "URGENT": "#BA7517", "STANDARD": "#185FA5" };

async function init() {
  try {
    const data = await api.get("/api/dashboard");
    content.innerHTML = render(data);
    brancherLogout();
  } catch (err) {
    content.innerHTML = `<div class="alert alert-error">Erreur : ${err.message}</div>`;
  }
}

function render(d) {
  return `
    <div class="dash-grid">
      ${cardDonutSla(d.repartition_sla, d.kpi)}
      ${cardCalendrier(d.aujourd_hui, d.echeances_jour, d.kpi)}
      ${cardEvolution(d.volume_mensuel)}
      ${cardKpiTuiles(d.kpi)}

      ${cardRepartitionCategorie(d.repartition_categorie)}
      ${cardRepartitionCanal(d.repartition_canal)}
      ${cardRepartitionPriorite(d.repartition_priorite)}

      ${cardAlertesSla(d.alertes_sla)}
      ${cardVolumeHebdo(d.volume_hebdo)}
    </div>
  `;
}

function cardDonutSla(repartition, kpi) {
  const segments = repartition.map(r => ({
    label: r.label, valeur: r.valeur, couleur: COULEURS_SLA[r.label],
  }));
  const totalActif = segments.filter(s => s.label !== "Terminé").reduce((a, b) => a + b.valeur, 0) || 1;
  const conforme = segments.find(s => s.label === "Conforme")?.valeur || 0;
  const pct = Math.round((conforme / totalActif) * 100);
  return `
    <div class="card col-4">
      <div class="card-head"><span class="card-title">Conformité SLA</span></div>
      <div class="donut-wrap">
        <div style="position:relative">
          ${donutSvg(segments, { size: 130, thickness: 16 })}
          <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center">
            <div style="font-size:24px;font-weight:700;color:#185FA5;line-height:1">${pct}%</div>
            <div style="font-size:10px;color:#6B6862">conforme</div>
          </div>
        </div>
        ${legendHtml(segments)}
      </div>
    </div>`;
}

function cardCalendrier(dateStr, echeancesJour, kpi) {
  const d = new Date(dateStr + "T00:00:00");
  const mois = d.toLocaleDateString("fr-FR", { month: "long" }).toUpperCase();
  const annee = d.getFullYear();
  return `
    <div class="card col-3">
      <div class="card-head"><span class="card-title">Aujourd'hui</span></div>
      <div class="calendar">
        <div class="mois">${mois} ${annee}</div>
        <div class="jour">${d.getDate()}</div>
        <div class="alerte-jour">
          ${echeancesJour > 0
            ? `<strong>${echeancesJour}</strong> échéance${echeancesJour > 1 ? "s" : ""} aujourd'hui`
            : "Aucune échéance aujourd'hui"}
        </div>
      </div>
      <div style="margin-top:12px;font-size:12px;color:var(--text-soft)">
        Reçues ce mois : <strong style="color:var(--text)">${kpi.recues_mois}</strong><br>
        Clôturées ce mois : <strong style="color:var(--text)">${kpi.cloturees}</strong>
      </div>
    </div>`;
}

function cardEvolution(volumeMensuel) {
  const labels = volumeMensuel.map(v => v.mois);
  const series = [
    { label: "Reçues",    valeurs: volumeMensuel.map(v => v.recues),    couleur: "#185FA5" },
    { label: "Clôturées", valeurs: volumeMensuel.map(v => v.cloturees), couleur: "#1D9E75" },
  ];
  return `
    <div class="card col-5">
      <div class="card-head">
        <span class="card-title">Évolution mensuelle</span>
        <div style="display:flex;gap:14px">
          <span style="font-size:11px;color:#6B6862">
            <span style="color:#185FA5;font-weight:600">●</span> Reçues
          </span>
          <span style="font-size:11px;color:#6B6862">
            <span style="color:#1D9E75;font-weight:600">●</span> Clôturées
          </span>
        </div>
      </div>
      ${lineChartSvg(labels, series, { width: 540, height: 220 })}
    </div>`;
}

function cardKpiTuiles(kpi) {
  const tuiles = [
    { l: "Reçues / mois", v: kpi.recues_mois },
    { l: "En cours", v: kpi.en_cours },
    { l: "Alerte SLA", v: kpi.en_alerte_sla },
    { l: "SLA échus", v: kpi.sla_depasses },
    { l: "Clôturées", v: kpi.cloturees },
    { l: "% sous 5j", v: kpi.taux_resolution_5j + "%" },
  ];
  return `
    <div class="card col-12">
      <div class="card-head"><span class="card-title">Indicateurs clés</span></div>
      <div class="kpi-row" style="grid-template-columns:repeat(6,1fr)">
        ${tuiles.map(t => `
          <div class="mini-kpi">
            <div class="v">${t.v}</div>
            <div class="l">${t.l}</div>
          </div>`).join("")}
      </div>
    </div>`;
}

function cardRepartitionCategorie(rep) {
  return `
    <div class="card col-4">
      <div class="card-head"><span class="card-title">Par catégorie</span></div>
      ${rep.length === 0
        ? `<div class="empty">Aucune donnée</div>`
        : rep.map((r, i) => hbarRow(r.label, r.valeur, r.pourcentage, couleurPour(i))).join("")}
    </div>`;
}

function cardRepartitionCanal(rep) {
  const segments = rep.map((r, i) => ({ label: r.label, valeur: r.valeur, couleur: couleurPour(i) }));
  return `
    <div class="card col-4">
      <div class="card-head"><span class="card-title">Par canal d'entrée</span></div>
      <div class="donut-wrap">
        ${donutSvg(segments, { size: 110, thickness: 12 })}
        ${legendHtml(segments)}
      </div>
    </div>`;
}

function cardRepartitionPriorite(rep) {
  return `
    <div class="card col-4">
      <div class="card-head"><span class="card-title">Par priorité</span></div>
      ${rep.length === 0
        ? `<div class="empty">Aucune donnée</div>`
        : rep.map(r => hbarRow(r.label, r.valeur, r.pourcentage,
            COULEURS_PRIO[r.label] || "#185FA5")).join("")}
    </div>`;
}

function hbarRow(label, valeur, pct, couleur) {
  return `
    <div class="hbar-row">
      <div class="hbar-lbl">${label}</div>
      <div class="hbar-track"><div class="hbar-fill" style="width:${pct}%;background:${couleur}"></div></div>
      <div class="hbar-val">${valeur}</div>
    </div>`;
}

function cardAlertesSla(alertes) {
  return `
    <div class="card col-8">
      <div class="card-head">
        <span class="card-title">Dossiers en alerte SLA</span>
        <a href="/reclamations.html?en_alerte=true" style="font-size:12px;color:var(--brand);text-decoration:none">Voir tout →</a>
      </div>
      ${alertes.length === 0
        ? `<div class="empty">Aucune alerte SLA — situation nominale.</div>`
        : `<table class="tbl">
            <thead><tr>
              <th>Dossier</th><th>Client</th><th>Catégorie</th><th>Priorité</th><th>SLA</th><th>Statut</th>
            </tr></thead>
            <tbody>${alertes.map(r => `
              <tr onclick="location='/detail.html?code=${r.code}'">
                <td><span class="code">${r.code}</span></td>
                <td>${r.client.prenom} ${r.client.nom}</td>
                <td>${r.sous_categorie || r.categorie}</td>
                <td>${pillPriorite(r.priorite)}</td>
                <td>${pillSla(r.sla_statut, r.sla_pourcentage)}</td>
                <td>${pillStatut(r.statut)}</td>
              </tr>`).join("")}</tbody>
          </table>`}
    </div>`;
}

function cardVolumeHebdo(volumeHebdo) {
  const labels = volumeHebdo.map(v => v.semaine);
  const series = [
    { label: "Reçues", valeurs: volumeHebdo.map(v => v.recues), couleur: "#B5D4F4" },
    { label: "Clôturées", valeurs: volumeHebdo.map(v => v.cloturees), couleur: "#185FA5" },
  ];
  return `
    <div class="card col-4">
      <div class="card-head">
        <span class="card-title">Volume hebdomadaire</span>
      </div>
      ${barChartSvg(labels, series, { width: 360, height: 180 })}
      <div style="margin-top:8px;font-size:11px;color:var(--text-soft);display:flex;gap:14px">
        <span><span style="color:#B5D4F4;font-weight:600">■</span> Reçues</span>
        <span><span style="color:#185FA5;font-weight:600">■</span> Clôturées</span>
      </div>
    </div>`;
}

init();
