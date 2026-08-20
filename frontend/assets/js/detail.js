// Vue détail d'une réclamation : timeline + actions de workflow.
if (!requireAuth()) throw new Error("redirect");
document.getElementById("app").innerHTML = renderLayout("liste", "Détail du dossier");
brancherLogout();
const content = document.getElementById("content");

const code = new URLSearchParams(location.search).get("code");
if (!code) {
  content.innerHTML = `<div class="alert alert-error">Aucun code de dossier fourni.</div>`;
} else {
  charger();
}

const TRANSITIONS = {
  NOUVEAU:   ["QUALIF", "REJETE"],
  QUALIF:    ["AFFECTE", "REJETE"],
  AFFECTE:   ["EN_COURS"],
  EN_COURS:  ["ATT_CLIENT", "VALIDATION", "ALERTE", "ESCALADE"],
  ATT_CLIENT:["EN_COURS"],
  ALERTE:    ["EN_COURS", "ESCALADE"],
  ESCALADE:  ["EN_COURS", "VALIDATION"],
  VALIDATION:["DECISION", "EN_COURS"],
  DECISION:  ["CLOTURE", "REOUVRE"],
  CLOTURE:   ["REOUVRE"],
  REOUVRE:   ["EN_COURS"],
};
const MOTIFS = ["FAVORABLE", "PARTIEL", "DEFAVORABLE", "SANS_SUITE", "MEDIATION"];

async function charger() {
  content.innerHTML = `<div class="card">Chargement…</div>`;
  try {
    const [d, agents, equipes, pjs] = await Promise.all([
      api.get(`/api/reclamations/${code}`),
      api.get("/api/agents"),
      api.get("/api/equipes"),
      api.get(`/api/reclamations/${code}/pieces-jointes`),
    ]);
    content.innerHTML = render(d, agents, equipes, pjs);
    brancher(d);
  } catch (err) {
    content.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

function render(d, agents, equipes, pjs) {
  const transitionsDispo = (TRANSITIONS[d.statut] || []).filter(s => s !== "CLOTURE");
  const peutCloturer = auth.isAdmin() &&
    (d.statut === "DECISION" || d.statut === "VALIDATION" || d.statut === "EN_COURS");

  const interactionsHtml = d.interactions.length === 0
    ? `<div class="empty">Aucun événement enregistré.</div>`
    : d.interactions.map(i => `
      <div class="timeline-item">
        <div><strong>${i.type}</strong> — ${i.contenu}</div>
        <div class="timeline-meta">
          ${formaterDate(i.date_heure)} · par ${i.auteur}
          ${i.valeur_avant ? ` · avant: <code>${i.valeur_avant}</code> → après: <code>${i.valeur_apres}</code>` : ""}
        </div>
      </div>`).join("");

  return `
    <div id="alerte"></div>
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
          <div style="font-size:11px;color:var(--text-soft)">DOSSIER</div>
          <div style="font-size:20px;font-weight:600" class="code">${d.code}</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          ${pillStatut(d.statut)} ${pillPriorite(d.priorite)} ${pillSla(d.sla_statut, d.sla_pourcentage)}
        </div>
      </div>
      <hr style="border:0;border-top:1px solid var(--border);margin:14px 0">
      <div class="form-grid">
        <div><label>Client</label><div>${d.client.prenom} ${d.client.nom}</div></div>
        <div><label>Contact</label><div>${d.client.email || "—"}<br>${d.client.telephone || ""}</div></div>
        <div><label>Canal</label><div>${d.canal}</div></div>
        <div><label>Catégorie</label><div>${d.categorie}${d.sous_categorie ? " · " + d.sous_categorie : ""}</div></div>
        <div><label>Montant en jeu</label><div>${d.montant_enjeu.toLocaleString("fr-FR")} FCFA</div></div>
        <div><label>Reçue le</label><div>${formaterDate(d.date_reception)}</div></div>
        <div><label>Échéance SLA</label><div>${formaterDate(d.date_echeance_sla)} (${d.sla_pourcentage}% consommé)</div></div>
        <div><label>Équipe affectée</label><div>${d.equipe_affectee ? d.equipe_affectee.libelle : "—"}</div></div>
        <div><label>Agent affecté</label><div>${d.agent_affecte ? `${d.agent_affecte.prenom} ${d.agent_affecte.nom}` : "—"}</div></div>
        <div class="full"><label>Description</label><div>${d.description}</div></div>
        ${d.motif_cloture ? `<div class="full"><label>Motif de clôture</label><div>${d.motif_cloture} — clôturé le ${formaterDate(d.date_cloture)}</div></div>` : ""}
      </div>
    </div>

    <div class="row-cols-2">
      <div class="card">
        <div class="card-head"><span class="card-title">Actions</span></div>

        ${transitionsDispo.length > 0 ? `
          <div style="margin-bottom:14px">
            <label>Changer de statut</label>
            <div style="display:flex;gap:8px">
              <select id="nouveau_statut">
                ${transitionsDispo.map(s => `<option>${s}</option>`).join("")}
              </select>
              <button class="btn btn-primary" id="btn_statut">Appliquer</button>
            </div>
          </div>` : ""}

        <div style="margin-bottom:14px">
          <label>Affecter à un agent</label>
          <div style="display:flex;gap:8px">
            <select id="agent">
              ${agents.map(a => `<option value="${a.id}">${a.prenom} ${a.nom} — ${a.service || a.role}</option>`).join("")}
            </select>
            <button class="btn" id="btn_affect">Affecter</button>
          </div>
        </div>

        <div style="margin-bottom:14px;padding-top:14px;border-top:1px solid var(--border)">
          <label>Transférer vers une autre équipe</label>
          <div style="display:flex;gap:8px;margin-bottom:6px">
            <select id="equipe_cible">
              ${equipes.filter(e => e.id !== (d.equipe_affectee && d.equipe_affectee.id))
                       .map(e => `<option value="${e.id}">${e.libelle}</option>`).join("")}
            </select>
          </div>
          <input id="motif_transfert" placeholder="Motif du transfert (obligatoire)…" style="margin-bottom:6px">
          <button class="btn btn-primary" id="btn_transfert">📤 Transférer & notifier l'équipe</button>
        </div>

        <div style="margin-bottom:14px">
          <label>Ajouter un commentaire</label>
          <textarea id="cmt" placeholder="Ajoute une note traçable au dossier"></textarea>
          <button class="btn" id="btn_cmt" style="margin-top:6px">Ajouter</button>
        </div>

        ${peutCloturer ? `
          <div style="margin-top:14px;padding-top:14px;border-top:1px solid var(--border)">
            <label>Clôturer le dossier (motif obligatoire — RG008)</label>
            <div style="display:flex;gap:8px">
              <select id="motif">${MOTIFS.map(m => `<option>${m}</option>`).join("")}</select>
              <button class="btn btn-danger" id="btn_clot">Clôturer</button>
            </div>
          </div>` : ""}
      </div>

      <div class="card">
        <div class="card-head"><span class="card-title">Journal d'audit (immuable)</span></div>
        <div>${interactionsHtml}</div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <span class="card-title">Pièces jointes (${pjs.length})</span>
        <label for="pj_upload" class="btn btn-primary" style="cursor:pointer">+ Ajouter un fichier</label>
        <input type="file" id="pj_upload" style="display:none">
      </div>
      ${pjs.length === 0
        ? `<div class="empty">Aucune pièce jointe.</div>`
        : `<table class="tbl">
            <thead><tr><th>Nom</th><th>Type</th><th>Taille</th><th>Auteur</th><th>Date</th><th></th></tr></thead>
            <tbody>${pjs.map(p => `
              <tr>
                <td><strong>${p.nom_fichier}</strong></td>
                <td style="font-size:12px;color:var(--text-soft)">${p.type_mime}</td>
                <td style="font-size:12px;color:var(--text-soft)">${(p.taille_octets / 1024).toFixed(1)} Ko</td>
                <td style="font-size:12px;color:var(--text-soft)">${p.auteur}</td>
                <td style="font-size:12px;color:var(--text-soft)">${formaterDate(p.date_upload)}</td>
                <td><button class="btn btn-pj-dl" data-id="${p.id}" data-nom="${p.nom_fichier}">📥 Télécharger</button></td>
              </tr>`).join("")}</tbody>
          </table>`}
    </div>

    <div class="card" style="background:var(--brand-bg);border-color:var(--brand-light)">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
          <div style="font-weight:500;color:#0C447C">🔗 Lien de suivi public pour le client</div>
          <div style="font-size:11px;color:var(--text-soft);font-family:monospace;margin-top:4px">
            ${location.origin}/portail-suivi.html?token=${d.token_suivi || "(absent)"}
          </div>
        </div>
        <button class="btn" id="btn_copier_lien">📋 Copier le lien</button>
      </div>
    </div>
  `;
}

function brancher(d) {
  const code = d.code;
  const alerte = document.getElementById("alerte");
  const erreur = (e) => alerte.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  const succes = (m) => alerte.innerHTML = `<div class="alert alert-success">${m}</div>`;

  const btnStatut = document.getElementById("btn_statut");
  if (btnStatut) btnStatut.onclick = async () => {
    try {
      await api.post(`/api/reclamations/${code}/statut`, {
        nouveau_statut: document.getElementById("nouveau_statut").value,
      });
      succes("Statut mis à jour."); setTimeout(charger, 500);
    } catch (e) { erreur(e); }
  };

  document.getElementById("btn_affect").onclick = async () => {
    try {
      await api.post(`/api/reclamations/${code}/affectation`, {
        id_agent_affecte: parseInt(document.getElementById("agent").value, 10),
      });
      succes("Dossier affecté."); setTimeout(charger, 500);
    } catch (e) { erreur(e); }
  };

  document.getElementById("btn_transfert").onclick = async () => {
    const id_cible = parseInt(document.getElementById("equipe_cible").value, 10);
    const motif = document.getElementById("motif_transfert").value.trim();
    if (motif.length < 3) return erreur(new Error("Le motif du transfert est obligatoire (≥ 3 caractères)."));
    try {
      await api.post(`/api/reclamations/${code}/transfert`, { id_equipe_cible: id_cible, motif });
      succes("Dossier transféré. L'équipe destinataire a été notifiée.");
      setTimeout(charger, 600);
    } catch (e) { erreur(e); }
  };

  document.getElementById("btn_cmt").onclick = async () => {
    const contenu = document.getElementById("cmt").value.trim();
    if (!contenu) return;
    try {
      await api.post(`/api/reclamations/${code}/commentaire`, { contenu });
      succes("Commentaire ajouté."); setTimeout(charger, 500);
    } catch (e) { erreur(e); }
  };

  const btnClot = document.getElementById("btn_clot");
  if (btnClot) btnClot.onclick = async () => {
    try {
      await api.post(`/api/reclamations/${code}/cloture`, {
        motif: document.getElementById("motif").value,
      });
      succes("Dossier clôturé."); setTimeout(charger, 500);
    } catch (e) { erreur(e); }
  };

  const inputPj = document.getElementById("pj_upload");
  if (inputPj) inputPj.onchange = async () => {
    const file = inputPj.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) return erreur(new Error("Fichier > 10 Mo."));
    const fd = new FormData();
    fd.append("fichier", file);
    try {
      const res = await fetch(`/api/reclamations/${code}/pieces-jointes`, {
        method: "POST",
        headers: { "Authorization": "Bearer " + auth.token() },
        body: fd,
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({ detail: "Erreur upload" }));
        throw new Error(j.detail);
      }
      succes(`Fichier "${file.name}" téléversé.`); setTimeout(charger, 600);
    } catch (e) { erreur(e); }
  };

  document.querySelectorAll(".btn-pj-dl").forEach(b => b.onclick = async () => {
    try {
      const res = await fetch(`/api/pieces-jointes/${b.dataset.id}/telecharger`, {
        headers: { "Authorization": "Bearer " + auth.token() },
      });
      if (!res.ok) throw new Error("Téléchargement impossible (" + res.status + ")");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = b.dataset.nom; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { erreur(e); }
  });

  const btnLien = document.getElementById("btn_copier_lien");
  if (btnLien && d.token_suivi) btnLien.onclick = () => {
    const url = `${location.origin}/portail-suivi.html?token=${d.token_suivi}`;
    navigator.clipboard.writeText(url).then(
      () => succes("Lien copié dans le presse-papier."),
      () => erreur(new Error("Copie impossible.")),
    );
  };
}
