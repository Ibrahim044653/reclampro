// Enregistrement du Service Worker + soumission offline (queue locale).
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err) =>
      console.warn("SW register failed:", err),
    );
  });
}

// File offline simple — stockée dans localStorage (suffisant).
const OfflineQueue = {
  ajouter(payload) {
    const file = JSON.parse(localStorage.getItem("rp_offline_queue") || "[]");
    file.push({ id: Date.now(), payload, date: new Date().toISOString() });
    localStorage.setItem("rp_offline_queue", JSON.stringify(file));
  },
  lister() {
    return JSON.parse(localStorage.getItem("rp_offline_queue") || "[]");
  },
  vider() {
    localStorage.removeItem("rp_offline_queue");
  },
  async rejouer() {
    const file = this.lister();
    if (!file.length) return { rejoues: 0, restants: 0 };
    const restants = [];
    let ok = 0;
    for (const item of file) {
      try {
        const res = await fetch("/api/public/reclamations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(item.payload),
        });
        if (res.ok) ok++;
        else restants.push(item);
      } catch (e) {
        restants.push(item);
      }
    }
    localStorage.setItem("rp_offline_queue", JSON.stringify(restants));
    return { rejoues: ok, restants: restants.length };
  },
};

// Rejoue automatiquement la file dès qu'on revient en ligne
window.addEventListener("online", () => {
  OfflineQueue.rejouer().then((r) => {
    if (r.rejoues > 0) {
      console.info(`[PWA] ${r.rejoues} soumission(s) rejouée(s) après reconnexion.`);
    }
  });
});
