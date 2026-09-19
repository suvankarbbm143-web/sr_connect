const CACHE_NAME="sr-connect-v6";
const APP_SHELL=["/sr_connect/home","/assets/sr_connect/manifest.json"];
self.addEventListener("install",e=>e.waitUntil(caches.open(CACHE_NAME).then(c=>c.addAll(APP_SHELL).catch(()=>{})).then(()=>self.skipWaiting())));
self.addEventListener("activate",e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE_NAME).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener("fetch",e=>{const r=e.request;if(r.method!=="GET")return;if(new URL(r.url).pathname.startsWith("/api/"))return;e.respondWith(fetch(r).then(x=>{if(x&&x.ok){const c=x.clone();caches.open(CACHE_NAME).then(k=>k.put(r,c));}return x;}).catch(()=>caches.match(r).then(x=>x||caches.match("/sr_connect/home"))));});
