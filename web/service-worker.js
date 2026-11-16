const CACHE_NAME = "physio-shell-v20";
const SHELL_URLS = [
  "/",
  "/customer",
  "/static/mobile.html",
  "/static/fonts.css?v=10",
  "/static/fonts/lxgw-wenkai-gb-regular.woff2",
  "/static/fonts/lxgw-wenkai-gb-medium.woff2",
  "/static/fonts/glow-sans-sc-regular.woff2",
  "/static/fonts/glow-sans-sc-medium.woff2",
  "/static/fonts/glow-sans-sc-bold.woff2",
  "/static/fonts/noto-sans-sc-regular.woff2",
  "/static/fonts/noto-sans-sc-bold.woff2",
  "/static/fonts/noto-serif-sc-regular.woff2",
  "/static/fonts/noto-serif-sc-bold.woff2",
  "/static/styles.css?v=12",
  "/static/customer.css?v=6",
  "/static/app.js?v=17",
  "/static/customer.js?v=6",
  "/static/mobile.css?v=10",
  "/static/mobile.js?v=10",
  "/static/icon.svg?v=8",
  "/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)),
        ),
      ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const requestUrl = new URL(event.request.url);
  if (
    event.request.method !== "GET" ||
    requestUrl.origin !== self.location.origin ||
    requestUrl.pathname.startsWith("/api/")
  ) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(event.request);
        return cached || caches.match("/");
      }),
  );
});
