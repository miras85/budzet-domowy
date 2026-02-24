const CACHE_NAME = 'domowy-budzet-v8'; 

const ASSETS_TO_CACHE = [
    '/',
    '/static/style.css',
    '/static/manifest.json',
    '/static/icon_v2.png',
    
    // Lokalne pliki JS
    '/static/js/main.js',
    '/static/js/api.js',
    '/static/js/utils.js',
    '/static/js/charts.js',
    
    // Komponenty
    '/static/js/components/LoginView.js',
    '/static/js/components/DashboardView.js',
    '/static/js/components/AccountsView.js',
    '/static/js/components/GoalsView.js',
    '/static/js/components/PaymentsView.js',
    '/static/js/components/SettingsView.js',
    '/static/js/components/AddTransactionView.js',
    '/static/js/components/SearchView.js',
    '/static/js/components/ImportModal.js',
    '/static/js/components/TheNavigation.js'
];

self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Service Worker] Caching app shell (v3) - BEZ TAILWIND');
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keyList) => {
            return Promise.all(keyList.map((key) => {
                if (key !== CACHE_NAME) {
                    return caches.delete(key);
                }
            }));
        })
    );
    return self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    if (url.pathname.startsWith('/api') || url.pathname.startsWith('/token')) {
        return;
    }
    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});
