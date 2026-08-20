// Gestion utilisateurs — réservée à l'admin.
if (!requireAuth()) throw new Error("redirect");
if (!auth.isAdmin()) {
  alert("Accès réservé aux administrateurs.");
  location.href = "/";
  throw new Error("forbidden");
}

document.getElementById("app").innerHTML = renderLayout("utilisateurs", "Gestion des utilisateurs");
brancherLogout();
const content = document.getElementById("content");

const ROLES = ["AGENT", "GESTIONNAIRE", "SUPERVISEUR", "CONFORMITE", "ADMIN"];

async function charger() {
  content.innerHTML = `<div class="card">Chargement…</div>`;
  try {
    const list = await api.get("/api/users");
    content.innerHTML = render(list);
    brancher();
  } catch (err) {
    content.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

function render(list) {
  const moi = auth.user();
  return `
    <div id="alerte"></div>

    <div class="card">
      <div class="card-head">
        <span class="card-title">Créer un nouvel utilisateur</span>
      </div>
      <form id="frm_create" class="form-grid">
        <div><label>Nom *</label><input name="nom" required></div>
        <div><label>Prénom *</label><input name="prenom" required></div>
        <div><label>Email professionnel *</label><input name="email_pro" type="email" required></div>
        <div><label>Service</label><input name="service" placeholder="Front-office…"></div>
        <div><label>Identifiant * (min. 3 car.)</label><input name="username" required minlength="3"></div>
        <div><label>Mot de passe * (min. 6 car.)</label><input name="password" type="password" required minlength="6"></div>
        <div><label>Rôle *</label>
          <select name="role">${ROLES.map(r => `<option ${r === "AGENT" ? "selected" : ""}>${r}</option>`).join("")}</select>
        </div>
        <div style="display:flex;align-items:end">
          <button class="btn btn-primary" type="submit">Créer</button>
        </div>
      </form>
    </div>

    <div class="card">
      <div class="card-head"><span class="card-title">Utilisateurs (${list.length})</span></div>
      <table class="tbl">
        <thead><tr>
          <th>ID</th><th>Identifiant</th><th>Nom</th><th>Email</th>
          <th>Service</th><th>Rôle</th><th>Actif</th><th style="width:280px">Actions</th>
        </tr></thead>
        <tbody>
          ${list.map(u => `
            <tr data-id="${u.id}">
              <td>#${u.id}</td>
              <td><strong>${u.username || "<i style='color:#999'>—</i>"}</strong>${u.id === moi.id ? ' <span class="pill pill-blue">vous</span>' : ""}</td>
              <td>${u.prenom} ${u.nom}</td>
              <td style="font-size:12px;color:var(--text-soft)">${u.email_pro}</td>
              <td>${u.service || "—"}</td>
              <td>
                <select class="role-sel" data-id="${u.id}" ${u.id === moi.id ? "disabled" : ""}>
                  ${ROLES.map(r => `<option ${r === u.role ? "selected" : ""}>${r}</option>`).join("")}
                </select>
              </td>
              <td>${u.actif ? '<span class="pill pill-green">OUI</span>' : '<span class="pill pill-gray">non</span>'}</td>
              <td style="white-space:nowrap">
                <button class="btn btn-save" data-id="${u.id}">💾 Enregistrer</button>
                <button class="btn btn-pwd"  data-id="${u.id}" ${!u.username ? "disabled title='Aucun compte de connexion'" : ""}>🔑 Mdp</button>
                ${u.id === moi.id ? "" : `<button class="btn btn-toggle" data-id="${u.id}" data-actif="${u.actif}">${u.actif ? "🚫 Désactiver" : "✓ Réactiver"}</button>`}
              </td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function alerte(html, type = "success") {
  document.getElementById("alerte").innerHTML = `<div class="alert alert-${type}">${html}</div>`;
}

function brancher() {
  document.getElementById("frm_create").addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    try {
      const u = await api.post("/api/users", data);
      alerte(`Utilisateur <strong>${u.username}</strong> créé.`);
      setTimeout(charger, 500);
    } catch (err) { alerte(err.message, "error"); }
  });

  document.querySelectorAll(".btn-save").forEach(btn => btn.onclick = async () => {
    const id = btn.dataset.id;
    const role = document.querySelector(`.role-sel[data-id="${id}"]`).value;
    try {
      await apiRequest("PATCH", `/api/users/${id}`, { role });
      alerte("Rôle mis à jour.");
      setTimeout(charger, 400);
    } catch (err) { alerte(err.message, "error"); }
  });

  document.querySelectorAll(".btn-pwd").forEach(btn => btn.onclick = async () => {
    const id = btn.dataset.id;
    const mdp = prompt("Nouveau mot de passe (min. 6 caractères) :");
    if (!mdp) return;
    if (mdp.length < 6) return alerte("Mot de passe trop court.", "error");
    try {
      await api.post(`/api/users/${id}/password`, { new_password: mdp });
      alerte("Mot de passe réinitialisé.");
    } catch (err) { alerte(err.message, "error"); }
  });

  document.querySelectorAll(".btn-toggle").forEach(btn => btn.onclick = async () => {
    const id = btn.dataset.id;
    const actif = btn.dataset.actif === "true";
    if (actif && !confirm("Désactiver ce compte ? Il ne pourra plus se connecter.")) return;
    try {
      if (actif) await apiRequest("DELETE", `/api/users/${id}`);
      else       await apiRequest("PATCH",  `/api/users/${id}`, { actif: true });
      alerte(actif ? "Compte désactivé." : "Compte réactivé.");
      setTimeout(charger, 400);
    } catch (err) { alerte(err.message, "error"); }
  });
}

// L'api.js de base n'expose pas PATCH/DELETE — j'utilise apiRequest directement.
charger();
