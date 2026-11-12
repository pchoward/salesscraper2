/* Ephemeral, shopper-triggered results. This module never touches catalog data,
 * URL state, saved views or browser storage. */
(function(root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.ShredCatalogSearch = api;
})(typeof window === 'undefined' ? globalThis : window, function() {
    'use strict';
    const MAX_AGE = 600000;
    function safeURL(value) {
        if (typeof value !== 'string') return '';
        try { const u = new URL(value); return u.protocol === 'https:' && !u.username && !u.password ? value : ''; }
        catch (_) { return ''; }
    }
    function formatMoney(money) {
        if (!money || !Number.isSafeInteger(money.amount) || money.amount < 0 || !/^[A-Z]{3}$/.test(money.currency)) return '';
        try {
            const fmt = new Intl.NumberFormat('en-US', {style:'currency',currency:money.currency});
            return fmt.format(money.amount / 10 ** fmt.resolvedOptions().maximumFractionDigits);
        } catch (_) { return ''; }
    }
    function mount(win, hooks) {
        const doc = win.document;
        let config;
        try { config = JSON.parse(doc.getElementById('liveCatalogSettings')?.textContent || '{}'); } catch (_) { return null; }
        if (config.enabled !== true || !config.apiBase) return null;
        let endpoint;
        try {
            const base = new URL(config.apiBase);
            if (base.protocol !== 'https:' && !(base.protocol === 'http:' && ['localhost','127.0.0.1'].includes(base.hostname))) return null;
            endpoint = new URL('/v1/catalog-search', base);
        } catch (_) { return null; }
        const section = doc.getElementById('liveCatalogDeals'), grid = doc.getElementById('liveCatalogGrid');
        const input = doc.getElementById('searchInput');
        if (!section || !grid || !input) return null;
        let timer = 0, expiryTimer = 0, controller = null, generation = 0, activeQuery = '', expires = 0;
        const query = () => input.value.trim().replace(/\s+/g,' ');
        function clear() {
            clearTimeout(timer); clearTimeout(expiryTimer); controller?.abort(); controller = null;
            generation++; activeQuery = ''; expires = 0; section.hidden = true; grid.replaceChildren();
        }
        function sync() {
            // Restored bookmarks, saved views, Clear all and view switches may
            // change the query without input. They may hide results, never fetch.
            if (activeQuery && (query() !== activeQuery || !hooks.allowed() || Date.now() >= expires)) clear();
        }
        function card(item) {
            const url = safeURL(item?.url), now = formatMoney(item?.price), list = formatMoney(item?.list_price);
            if (!url || !now || !list || item.price.currency !== item.list_price.currency ||
                item.list_price.amount <= item.price.amount || item.price.amount > item.list_price.amount * .95 || !item.title) return null;
            const node = doc.createElement('article'); node.className = 'catalog-live-card';
            const link = doc.createElement('a'); link.href = url; link.rel = 'noopener'; link.className = 'catalog-live-link';
            const image = safeURL(item.image);
            if (image) { const img = doc.createElement('img'); img.src = image; img.alt = ''; img.loading = 'lazy'; link.appendChild(img); }
            const title = doc.createElement('span'); title.className = 'catalog-live-title'; title.textContent = item.title; link.appendChild(title); node.appendChild(link);
            const shop = doc.createElement('p'); shop.className = 'catalog-live-shop'; shop.textContent = item.seller?.name || new URL(url).hostname;
            const domain = item.seller?.domain;
            if (domain && domain !== item.seller?.name) { const small = doc.createElement('small'); small.textContent = domain; shop.appendChild(small); }
            node.appendChild(shop);
            const price = doc.createElement('p'); price.className = 'catalog-live-price';
            const strong = doc.createElement('strong'); strong.textContent = now;
            const was = doc.createElement('s'); was.textContent = list;
            const discount = doc.createElement('span'); discount.textContent = Math.floor((item.list_price.amount-item.price.amount)*100/item.list_price.amount)+'% off';
            price.append(strong, was, discount); node.appendChild(price); return node;
        }
        input.addEventListener('input', () => {
            clear(); const text = query();
            if (text.length < 3 || text.length > 200 || !hooks.allowed()) return;
            const current = generation;
            timer = win.setTimeout(async () => {
                if (current !== generation || query() !== text || !hooks.allowed()) return;
                const request = new URL(endpoint); request.searchParams.set('q', text); request.searchParams.set('sport', hooks.sport());
                controller = new AbortController(); const ownController = controller;
                const timeout = win.setTimeout(() => ownController.abort(), 10000);
                const startedAt = Date.now();
                try {
                    const response = await win.fetch(request.href, {signal:ownController.signal,credentials:'omit',cache:'no-store'});
                    if (!response.ok) throw new Error('unavailable');
                    const data = await response.json();
                    if (current !== generation || query() !== text || !hooks.allowed()) return;
                    // Remaining server TTL, reduced by round-trip time, avoids extending
                    // cached prices on phones whose clock differs from the server.
                    const remaining = Number(data.max_age_ms);
                    const until = Date.now() + Math.min(MAX_AGE, Number.isFinite(remaining) ? remaining : 0) - (Date.now()-startedAt);
                    if (until <= Date.now()) return;
                    const nodes = (Array.isArray(data.items) ? data.items.slice(0,12) : []).map(card).filter(Boolean);
                    if (!nodes.length) return;
                    grid.replaceChildren(...nodes); section.hidden = false; activeQuery = text; expires = until;
                    expiryTimer = win.setTimeout(clear, Math.max(0, until-Date.now()));
                } catch (_) { if (current === generation) clear(); }
                finally { clearTimeout(timeout); }
            }, 400);
        });
        doc.addEventListener('visibilitychange', sync);
        win.addEventListener('pagehide', clear);
        win.addEventListener('pageshow', sync);
        return {sync, clear};
    }
    return {mount, formatMoney};
});
