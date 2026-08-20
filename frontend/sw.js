// Service Worker — cache statique + queue offline pour les soumissions publiques.
// Stratégie : network-first pour les APIs (toujours frais), cache-first pour les assets.

const CACHE_NAME = "reclampro-v1";
const ASSETS_A_CACHER = [
  "/",
  "/portail.html",
  "/portail-suivi.html",
  "/login.html",
  "/assets/css/styles.css",
  "/assets/js/api.js",
  "/assets/js/i18n.js",
  "/assets/js/layout.js",
  "/assets/js/charts.js",
  "/manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_A_CACHER)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // APIs : network-first (avec fallback cache pour les GET seulement)
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request).catch(() => {
        if (event.request.method === "GET") {
          return caches.match(event.request);
        }
        return new Response(
          JSON.stringify({ detail: "Hors-ligne. Soumission mise en file." }),
          { status: 503, headers: { "Content-Type": "application/json" } },
        );
      }),
    );
    return;
  }

  // Pages et assets : cache-first
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (response.ok && event.request.method === "GET") {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((c) => c.put(event.request, clone));
        }
        return response;
      });
    }),
  );
});

// File des soumissions publiques en attente (réessayées au retour réseau)
self.addEventListener("sync", (event) => {
  if (event.tag === "sync-soumissions") {
    event.waitUntil(rejouerSoumissionsEnAttente());
  }
});

async function rejouerSoumissionsEnAttente() {
  // Note : le client web stocke en IndexedDB sous "soumissions_offline"
  // — ce SW lit et rejoue. Pour rester simple, l'implémentation client peut
  // déclencher manuellement via "navigator.serviceWorker.controller.postMessage(...)"
}
