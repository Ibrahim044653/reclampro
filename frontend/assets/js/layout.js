// Layout commun à toutes les pages : sidebar + topbar + bandeau utilisateur.
function renderLayout(pageActive, titre) {
  const u = auth.user();
  const estAdmin = auth.isAdmin();
  const initiales = u ? (u.prenom[0] + u.nom[0]).toUpperCase() : "?";
  const t = (cle) => (typeof i18n !== "undefined" ? i18n.t(cle) : cle);
  const langCourante = (typeof i18n !== "undefined") ? i18n.lang() : "fr";

  const items = [
    { id: "dashboard",    href: "/",                         label: t("Tableau de bord"),      section: t("Pilotage"), adminOnly: false },
    { id: "reportings",   href: "/reportings.html",          label: t("Reportings"),           section: t("Pilotage"), adminOnly: true },
    { id: "ma-file",      href: "/ma-file.html",             label: t("Ma file"),              section: t("Mon espace"), adminOnly: false },
    { id: "notifications",href: "/notifications.html",       label: t("Notifications"),       section: t("Mon espace"), adminOnly: false },
    { id: "mfa",          href: "/mfa.html",                 label: t("Sécurité (MFA)"),       section: t("Mon espace"), adminOnly: false },
    { id: "liste",        href: "/reclamations.html",        label: t("Réclamations"),         section: t("Dossiers"), adminOnly: false },
    { id: "nouvelle",     href: "/nouvelle.html",            label: t("Nouveau dossier"),      section: t("Dossiers"), adminOnly: false },
    { id: "registre",     href: "/api/exports/registre.csv", label: t("Registre BCEAO (CSV)"), section: t("Conformité"), adminOnly: true },
    { id: "utilisateurs", href: "/utilisateurs.html",        label: t("Utilisateurs"),         section: t("Administration"), adminOnly: true },
  ].filter(it => !it.adminOnly || estAdmin);

  const groupes = {};
  items.forEach(it => { (groupes[it.section] ||= []).push(it); });
  const navHtml = Object.entries(groupes).map(([sec, list]) => `
    <div class="nav-section">${sec}</div>
    ${list.map(it => `
      <a class="nav-item ${it.id === pageActive ? "active" : ""}" href="${it.href}">${it.label}</a>
    `).join("")}
  `).join("");

  const exportBtn = estAdmin
    ? `<a class="btn" href="/api/exports/registre.csv?token=${auth.token()}" id="btn_export_topbar">📥 Exporter</a>`
    : "";

  return `
    <div class="shell">
      <div class="sidebar">
        <div class="logo">
          <div class="logo-icon">R</div>
          <div>
            <div class="logo-text">RéclamPro</div>
            <div class="logo-sub">MVP — Banque/Assurance CI</div>
          </div>
        </div>
        <div class="nav">${navHtml}</div>
        <div style="padding:8px 12px;border-top:1px solid var(--border);display:flex;align-items:center;gap:6px;font-size:11px">
          <span style="color:var(--text-soft)">🌐</span>
          <button class="btn" id="btn_lang_fr" style="padding:2px 8px;${langCourante === "fr" ? "background:var(--brand);color:#fff" : ""}">FR</button>
          <button class="btn" id="btn_lang_en" style="padding:2px 8px;${langCourante === "en" ? "background:var(--brand);color:#fff" : ""}">EN</button>
        </div>
        <div style="padding:12px;border-top:1px solid var(--border);display:flex;align-items:center;gap:8px">
          <div style="width:30px;height:30px;border-radius:50%;background:var(--brand-bg);color:var(--brand);display:flex;align-items:center;justify-content:center;font-weight:600;font-size:12px">${initiales}</div>
          <div style="flex:1;min-width:0">
            <div style="font-size:12px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${u ? u.prenom + " " + u.nom : ""}</div>
            <div style="font-size:10px;color:var(--text-soft)">${u ? u.role : ""}</div>
          </div>
          <button class="btn" id="btn_logout" title="Se déconnecter" style="padding:4px 8px">↪</button>
        </div>
      </div>
      <div class="main">
        <div class="topbar">
          <div class="topbar-title">${titre}</div>
          <a class="btn" id="btn_notifs" href="/notifications.html" title="Notifications" style="position:relative">
            🔔 <span id="notif_badge" style="display:none;position:absolute;top:-4px;right:-4px;background:#E24B4A;color:#fff;border-radius:10px;padding:1px 6px;font-size:10px;font-weight:600">0</span>
          </a>
          ${exportBtn}
          <a class="btn btn-primary" href="/nouvelle.html">+ Nouveau dossier</a>
        </div>
        <div class="content" id="content"></div>
      </div>
    </div>
  `;
}

// Met à jour le badge de notifications dans la topbar (toutes les 30 s).
async function rafraichirBadgeNotifs() {
  try {
    const d = await api.get("/api/notifications/count");
    const badge = document.getElementById("notif_badge");
    if (!badge) return;
    if (d.non_lues > 0) {
      badge.style.display = "inline-block";
      badge.textContent = d.non_lues > 99 ? "99+" : d.non_lues;
    } else {
      badge.style.display = "none";
    }
  } catch (e) { /* silencieux */ }
}

// Branche le bouton logout après le rendu.
function brancherLogout() {
  const btn = document.getElementById("btn_logout");
  if (btn) btn.onclick = () => auth.logout();
  const fr = document.getElementById("btn_lang_fr");
  const en = document.getElementById("btn_lang_en");
  if (fr) fr.onclick = () => (typeof i18n !== "undefined" ? i18n.setLang("fr") : null);
  if (en) en.onclick = () => (typeof i18n !== "undefined" ? i18n.setLang("en") : null);
  rafraichirBadgeNotifs();
  setInterval(rafraichirBadgeNotifs, 30000);
  // Pour l'export, on doit envoyer le token dans le header — clic intercepté.
  const exp = document.getElementById("btn_export_topbar");
  if (exp) exp.onclick = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch("/api/exports/registre.csv", {
        headers: { "Authorization": "Bearer " + auth.token() },
      });
      if (!res.ok) throw new Error("Export impossible (" + res.status + ")");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "registre_reclamations.csv"; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { alert(err.message); }
  };
}
