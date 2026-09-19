const CACHE_VERSION = "sr-connect-home-v1";

self.addEventListener("install", (event) => {
    event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((key) => key !== CACHE_VERSION)
                    .map((key) => caches.delete(key))
            )
        ).then(() => self.clients.claim())
    );
});

/*
 * SR Connect is an ERP portal.
 * Do not cache ERP HTML/API responses.
 * The fetch handler keeps the PWA service-worker requirement
 * while allowing every request to continue to the live server.
 */
self.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") {
        return;
    }

    if (event.request.mode === "navigate") {
        event.respondWith(fetch(event.request));
    }
});
