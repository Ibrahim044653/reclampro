// Liste et gestion des notifications de l'utilisateur courant.
if (!requireAuth()) throw new Error("redirect");
document.getElementById("app").innerHTML = renderLayout("notifications", "Mes notifications");
brancherLogout();
const content = document.getElementById("content");

async function charger() {
  content.innerHTML = `<div class="card">Chargement…</div>`;
  try {
    const list = await api.get("/api/notifications");
    content.innerHTML = render(list);
    brancher();
  } catch (err) {
    content.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

function render(list) {
  const nbNonLues = list.filter(n => !n.lue).length;
  const filtre = `
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
          <span class="card-title">${list.length} notification${list.length > 1 ? "s" : ""}</span>
          ${nbNonLues > 0 ? `<span class="pill pill-red" style="margin-left:8px">${nbNonLues} non lue${nbNonLues > 1 ? "s" : ""}</span>` : ""}
        </div>
        <button class="btn" id="btn_tout_lu" ${nbNonLues === 0 ? "disabled" : ""}>Tout marquer comme lu</button>
      </div>
    </div>`;

  if (list.length === 0) {
    return filtre + `<div class="card empty">Aucune notification.</div>`;
  }

  const items = list.map(n => `
    <div class="card" style="display:flex;align-items:center;gap:14px;${n.lue ? "" : "border-left:3px solid var(--brand)"}">
      <div style="font-size:22px">${iconePour(n.type)}</div>
      <div style="flex:1;min-width:0">
        <div style="font-weight:${n.lue ? "400" : "600"};margin-bottom:2px">${esc(n.contenu)}</div>
        <div style="font-size:11px;color:var(--text-soft)">
          ${n.type} · ${formaterDate(n.date_creation)}
          ${n.code_reclamation ? ` · <a href="/detail.html?code=${n.code_reclamation}" style="color:var(--brand)">${n.code_reclamation}</a>` : ""}
        </div>
      </div>
      ${n.lue
        ? `<span class="pill pill-gray">Lue</span>`
        : `<button class="btn btn-marquer" data-id="${n.id}">Marquer lue</button>`}
    </div>`).join("");

  return filtre + items;
}

function iconePour(type) {
  return ({ TRANSFERT: "📤", AFFECTATION: "👤", ECHEANCE: "⏰", ALERTE: "⚠️" }[type]) || "🔔";
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;" }[c]));
}

function brancher() {
  document.querySelectorAll(".btn-marquer").forEach(b => b.onclick = async () => {
    try {
      await api.post(`/api/notifications/${b.dataset.id}/lue`);
      charger();
    } catch (e) { alert(e.message); }
  });
  const btnTout = document.getElementById("btn_tout_lu");
  if (btnTout) btnTout.onclick = async () => {
    try {
      await api.post(`/api/notifications/toutes-lues`);
      charger();
    } catch (e) { alert(e.message); }
  };
}

charger();
