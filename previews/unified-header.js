/* Shared native-page header. The renderer supplies URLs; no catalog/iframe logic. */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else {
        root.ShredHeader = api;
        const start = () => {
            const config = document.getElementById('shredHeaderConfig');
            if (config) api.mount(document, JSON.parse(config.textContent));
        };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
        else start();
    }
})(typeof window === 'undefined' ? this : window, function () {
    'use strict';
    function pageURL(href, base) {
        const url = new URL(href, base);
        if (url.origin !== new URL(base).origin || url.username || url.password || !/^https?:$/.test(url.protocol)) throw new Error('Sport pages must be same-origin HTTP(S) URLs');
        return url;
    }
    function validate(config, base) {
        if (!Array.isArray(config.sports) || !config.sports.length) throw new Error('Sports are required');
        const ids = new Set();
        config.sports.forEach(sport => {
            if (!/^[a-z][a-z0-9-]*$/.test(sport.id) || ids.has(sport.id) || !sport.label) throw new Error('Invalid sport');
            ids.add(sport.id);
            if (typeof sport.href !== 'string' || !sport.href) throw new Error('Sport URL is required');
            pageURL(sport.href, base);
            (sport.aliases || []).forEach(href => pageURL(href, base));
        });
        if (!ids.has(config.currentSport)) throw new Error('Unknown current sport');
        return config;
    }
    function nextIndex(index, key, count) {
        if (key === 'Home') return 0;
        if (key === 'End') return count - 1;
        if (key === 'ArrowRight') return (index + 1) % count;
        if (key === 'ArrowLeft') return (index + count - 1) % count;
        return null;
    }
    function mount(doc, config) {
        const win = doc.defaultView;
        validate(config, win.location.href);
        const bar = doc.querySelector('#stickyBar .topnav');
        if (!bar || bar.classList.contains('shred-header')) return;
        const brand = bar.querySelector('#homeReset');
        if (!brand) throw new Error('Header needs the existing homeReset control');
        bar.classList.add('shred-header');
        // Keep the original button and listeners, including its reset semantics.
        brand.textContent = config.brand || 'ShredDeals';
        const nav = doc.createElement('nav');
        nav.className = 'shred-sports';
        nav.setAttribute('aria-label', 'Sports');
        const current = config.sports.find(s => s.id === config.currentSport);
        const storageKey = 'shred-header:' + config.sports.map(s => pageURL(s.href, win.location.href).pathname).join('|');
        function saved() {
            try {
                const value = JSON.parse(win.sessionStorage.getItem(storageKey) || '{}');
                return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
            }
            catch (_) { return {}; }
        }
        function remember() {
            const state = saved();
            state[config.currentSport] = win.location.href;
            try { win.sessionStorage.setItem(storageKey, JSON.stringify(state)); } catch (_) { /* Storage is optional. */ }
        }
        function target(sport) {
            const target = pageURL(sport.href, win.location.href);
            const old = saved()[sport.id];
            if (old) {
                try {
                    const restored = pageURL(old, win.location.href);
                    const paths = [target.pathname].concat((sport.aliases || []).map(href => pageURL(href, win.location.href).pathname));
                    if (paths.includes(restored.pathname)) return restored.href;
                } catch (_) { /* Ignore stale or untrusted state. */ }
            }
            return target.href;
        }
        function refresh() {
            nav.querySelectorAll('a').forEach((link, i) => {
                const sport = config.sports[i];
                link.href = sport.id === config.currentSport ? win.location.href : target(sport);
            });
        }
        config.sports.forEach(sport => {
            const link = doc.createElement('a');
            link.textContent = sport.label;
            link.dataset.sport = sport.id;
            link.className = 'shred-sport';
            if (sport.id === config.currentSport) link.setAttribute('aria-current', 'page');
            link.addEventListener('click', event => {
                remember();
                refresh();
                // Selecting the already-active sport never clears filters/panels.
                if (sport.id === current.id && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && event.button === 0) event.preventDefault();
            });
            nav.appendChild(link);
        });
        nav.addEventListener('keydown', event => {
            const links = Array.from(nav.querySelectorAll('a'));
            const index = links.indexOf(doc.activeElement);
            const next = nextIndex(index, event.key, links.length);
            if (index >= 0 && next !== null) {
                event.preventDefault();
                links[next].focus(); // Enter follows the native link. Tab remains native.
            }
        });
        bar.querySelector('.brand').after(nav);
        refresh();
        // Native links/history, no pushState wrappers or competing URL owner.
        win.addEventListener('pagehide', remember);
        win.addEventListener('pageshow', refresh);
        const resize = () => {
            if (typeof win.measureBar === 'function') win.measureBar();
        };
        if (win.ResizeObserver) new win.ResizeObserver(resize).observe(bar);
        resize();
    }
    return {mount, validate, pageURL, nextIndex};
});
