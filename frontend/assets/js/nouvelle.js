// Formulaire de saisie d'une nouvelle réclamation.
if (!requireAuth()) throw new Error("redirect");
document.getElementById("app").innerHTML = renderLayout("nouvelle", "Nouveau dossier de réclamation");
brancherLogout();
const content = document.getElementById("content");

const SOUS_CATEGORIES = {
  FINANCIERE:    ["Débit non autorisé", "Virement erroné", "Frais contestés", "Remboursement sinistre"],
  CONTRACTUELLE: ["Non-respect des conditions", "Information erronée à la vente", "Résiliation abusive"],
  SERVICE:       ["Délai excessif", "Comportement agent", "Accès au service"],
  FRAUDE:        ["Usurpation identité", "Phishing / arnaque", "Fraude interne"],
};

content.innerHTML = `
  <div class="card" style="max-width:880px">
    <div class="card-head">
      <span class="card-title">Informations de la réclamation</span>
    </div>
    <div id="alerte"></div>
    <form id="frm" class="form-grid">
      <div>
        <label>Canal d'entrée *</label>
        <select name="canal" required>
          <option value="">— Choisir —</option>
          <option>EMAIL</option><option>AGENCE</option><option>TELEPHONE</option>
          <option>WEB</option><option>WHATSAPP</option><option>COURRIER</option>
        </select>
      </div>
      <div>
        <label>Catégorie *</label>
        <select name="categorie" id="categorie" required>
          <option value="">— Choisir —</option>
          <option>FINANCIERE</option><option>CONTRACTUELLE</option>
          <option>SERVICE</option><option>FRAUDE</option>
        </select>
      </div>
      <div>
        <label>Sous-catégorie</label>
        <select name="sous_categorie" id="sous_categorie">
          <option value="">— Choisir une catégorie d'abord —</option>
        </select>
      </div>
      <div>
        <label>Priorité *</label>
        <select name="priorite" required>
          <option value="STANDARD">STANDARD — 5 j ouvrés</option>
          <option value="URGENT">URGENT — 72 h</option>
          <option value="CRITIQUE">CRITIQUE — 24 h</option>
        </select>
      </div>
      <div>
        <label>Montant en jeu (FCFA)</label>
        <input name="montant_enjeu" type="number" min="0" step="100" value="0">
      </div>
      <div></div>

      <div class="full"><hr style="border:0;border-top:1px solid var(--border);margin:8px 0"></div>

      <div>
        <label>Nom du client *</label>
        <input name="nom" required>
      </div>
      <div>
        <label>Prénom du client *</label>
        <input name="prenom" required>
      </div>
      <div>
        <label>Email du client</label>
        <input name="email" type="email" placeholder="ex. fatou@example.ci">
      </div>
      <div>
        <label>Téléphone du client</label>
        <input name="telephone" placeholder="+225 …">
      </div>

      <div class="full">
        <label style="display:flex;justify-content:space-between;align-items:center">
          <span>Description détaillée * (10 caractères minimum)</span>
          <button type="button" class="btn" id="btn_ia" style="padding:4px 10px;font-size:11px">
            🤖 Suggérer catégorie + priorité (IA)
          </button>
        </label>
        <textarea name="description" id="description" required minlength="10"
          placeholder="Décrire les faits, dates, montants, références…"></textarea>
        <div id="suggestion_ia"></div>
      </div>

      <div class="full" style="display:flex;justify-content:flex-end;gap:8px">
        <a href="/reclamations.html" class="btn">Annuler</a>
        <button class="btn btn-primary" type="submit">Créer le dossier</button>
      </div>
    </form>
  </div>
`;

const selCategorie = document.getElementById("categorie");
const selSousCat = document.getElementById("sous_categorie");
selCategorie.addEventListener("change", () => {
  const liste = SOUS_CATEGORIES[selCategorie.value] || [];
  selSousCat.innerHTML = `<option value="">— Optionnel —</option>` +
    liste.map(s => `<option>${s}</option>`).join("");
});

document.getElementById("btn_ia").addEventListener("click", async () => {
  const desc = document.getElementById("description").value.trim();
  const zone = document.getElementById("suggestion_ia");
  if (desc.length < 5) {
    zone.innerHTML = `<div class="alert alert-error">Saisissez au moins 5 caractères de description.</div>`;
    return;
  }
  zone.innerHTML = `<div style="font-size:12px;color:var(--text-soft);margin-top:6px">Analyse…</div>`;
  try {
    const r = await api.post("/api/reclamations/suggerer-ia", { description: desc });
    const formCat = document.querySelector('select[name="categorie"]');
    const formPrio = document.querySelector('select[name="priorite"]');
    zone.innerHTML = `
      <div class="alert alert-success" style="font-size:12px;margin-top:6px">
        <div><strong>🤖 Suggestion IA :</strong> ${r.categorie_suggeree}
          (confiance ${(r.score_categorie*100).toFixed(0)} %) · Priorité ${r.priorite_suggeree}
          (confiance ${(r.score_priorite*100).toFixed(0)} %)</div>
        <div style="font-size:11px;margin-top:4px;color:#27500A">${r.explication}</div>
        ${r.voisins_similaires.length ? `
          <div style="font-size:11px;margin-top:4px">Dossiers similaires :
            ${r.voisins_similaires.map(v => `<code>${v.code}</code> (${v.categorie})`).join(", ")}
          </div>` : ""}
        <button type="button" class="btn btn-primary" style="margin-top:8px;padding:4px 10px;font-size:11px" id="btn_appliquer_ia">Appliquer ces valeurs</button>
      </div>`;
    document.getElementById("btn_appliquer_ia").onclick = () => {
      formCat.value = r.categorie_suggeree;
      formCat.dispatchEvent(new Event("change"));
      formPrio.value = r.priorite_suggeree;
    };
  } catch (e) {
    zone.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
});

document.getElementById("frm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = Object.fromEntries(new FormData(form).entries());
  const payload = {
    canal: data.canal,
    categorie: data.categorie,
    sous_categorie: data.sous_categorie || null,
    priorite: data.priorite,
    description: data.description,
    montant_enjeu: parseFloat(data.montant_enjeu || 0),
    client: {
      nom: data.nom,
      prenom: data.prenom,
      email: data.email || null,
      telephone: data.telephone || null,
    },
  };
  const alerte = document.getElementById("alerte");
  alerte.innerHTML = "";
  try {
    const res = await api.post("/api/reclamations", payload);
    alerte.innerHTML = `<div class="alert alert-success">Dossier créé : ${res.code}. Redirection…</div>`;
    setTimeout(() => location.href = `/detail.html?code=${res.code}`, 800);
  } catch (err) {
    alerte.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
});
