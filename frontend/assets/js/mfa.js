// Configuration de la double authentification TOTP (MFA).
if (!requireAuth()) throw new Error("redirect");
document.getElementById("app").innerHTML = renderLayout("mfa", "Sécurité — Double authentification");
brancherLogout();
const content = document.getElementById("content");

async function init() {
  try {
    const me = await api.get("/api/auth/me");
    content.innerHTML = render(me);
    brancher();
  } catch (err) {
    content.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
  }
}

function render(me) {
  if (me.mfa_active) {
    return `
      <div class="card" style="max-width:560px">
        <div class="card-head"><span class="card-title">MFA activée ✓</span></div>
        <div id="alerte"></div>
        <p style="font-size:13px;color:var(--text-soft);margin-bottom:14px">
          Votre compte est protégé par une double authentification. À chaque connexion,
          un code à 6 chiffres généré par votre application sera demandé.
        </p>
        <div style="border-top:1px solid var(--border);padding-top:14px">
          <label>Désactiver la MFA (saisissez votre mot de passe)</label>
          <input id="pwd" type="password" placeholder="Mot de passe actuel">
          <button class="btn btn-danger" id="btn_desactiver" style="margin-top:8px">Désactiver la MFA</button>
        </div>
      </div>`;
  }

  return `
    <div class="card" style="max-width:560px">
      <div class="card-head"><span class="card-title">Activer la double authentification</span></div>
      <div id="alerte"></div>
      <p style="font-size:13px;color:var(--text-soft);margin-bottom:14px">
        Renforcez votre sécurité avec un code à 6 chiffres généré par
        <strong>Google Authenticator</strong>, <strong>Authy</strong> ou tout équivalent
        compatible TOTP (RFC 6238).
      </p>
      <button class="btn btn-primary" id="btn_setup">Lancer la configuration</button>
    </div>
    <div id="setup_zone"></div>`;
}

function renderSetup(d) {
  return `
    <div class="card" style="max-width:560px">
      <div class="card-head"><span class="card-title">Étape 1 — Scanner le QR code</span></div>
      <p style="font-size:13px;color:var(--text-soft)">
        Ouvrez votre application d'authentification et scannez ce code :
      </p>
      <div style="text-align:center;padding:14px;background:#fff;border-radius:8px;border:1px solid var(--border)">
        <img src="data:image/png;base64,${d.qr_code_png_base64}" alt="QR MFA" style="max-width:200px">
      </div>
      <p style="font-size:11px;color:var(--text-soft);margin-top:8px">
        Code manuel (si vous ne pouvez pas scanner) :
        <code style="background:var(--bg);padding:2px 6px;border-radius:4px">${d.secret}</code>
      </p>

      <div style="margin-top:18px;padding-top:18px;border-top:1px solid var(--border)">
        <label>Étape 2 — Saisir le code à 6 chiffres affiché par l'application</label>
        <div style="display:flex;gap:8px;margin-top:6px">
          <input id="code_mfa" maxlength="6" pattern="[0-9]*" inputmode="numeric"
                 placeholder="123456" style="flex:1">
          <button class="btn btn-primary" id="btn_activer">Activer</button>
        </div>
      </div>
    </div>`;
}

function brancher() {
  const btnSetup = document.getElementById("btn_setup");
  if (btnSetup) btnSetup.onclick = async () => {
    try {
      const d = await api.post("/api/auth/mfa/setup");
      document.getElementById("setup_zone").innerHTML = renderSetup(d);
      document.getElementById("btn_activer").onclick = async () => {
        const code = document.getElementById("code_mfa").value.trim();
        try {
          await api.post("/api/auth/mfa/activate", { code });
          alerte("MFA activée avec succès. Reconnectez-vous pour vérifier.", "success");
          setTimeout(() => location.reload(), 1200);
        } catch (e) { alerte(e.message, "error"); }
      };
    } catch (e) { alerte(e.message, "error"); }
  };

  const btnDes = document.getElementById("btn_desactiver");
  if (btnDes) btnDes.onclick = async () => {
    const pwd = document.getElementById("pwd").value;
    if (!pwd) return alerte("Saisissez votre mot de passe.", "error");
    try {
      await api.post("/api/auth/mfa/desactiver", { password: pwd });
      alerte("MFA désactivée.", "success");
      setTimeout(() => location.reload(), 800);
    } catch (e) { alerte(e.message, "error"); }
  };
}

function alerte(msg, type) {
  const z = document.getElementById("alerte");
  if (z) z.innerHTML = `<div class="alert alert-${type}">${msg}</div>`;
}

init();
