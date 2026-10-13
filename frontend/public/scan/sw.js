// frontend/public/scan/sw.js
// 掃描頁的離線快取：打開過一次之後，斷網時重新整理也打得開。
// 只快取掃描頁自己的檔案（頁面與條碼辨識程式庫）；簽到紀錄存在 localStorage，由頁面自己上傳。
const CACHE = 'ncuacg-scan-v1';
const ASSETS = [
  './',
  './index.html',
  './vendor/zxing-library-0.21.3.min.js',
  './vendor/zxing-wasm-3.1.4/zxing-reader.iife.js',
  './vendor/zxing-wasm-3.1.4/zxing_reader.wasm',
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k.startsWith('ncuacg-scan-') && k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  // API 一律走網路（離線時由頁面自己處理）；其他網站的東西不管
  if (event.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return;

  if (event.request.mode === 'navigate') {
    // 頁面：有網路就拿最新的，沒網路才用快取（網址上的 ?event=&key= 不影響）
    event.respondWith(
      fetch(event.request)
        .then(res => { const copy = res.clone(); caches.open(CACHE).then(c => c.put('./index.html', copy)); return res; })
        .catch(() => caches.match('./index.html')),
    );
    return;
  }
  // 程式庫：版本號寫在路徑裡，直接用快取
  event.respondWith(caches.match(event.request).then(hit => hit || fetch(event.request)));
});
