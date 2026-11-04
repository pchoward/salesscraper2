// Shared same-origin shell bridge. Standalone SkateDeals pages remain independent.
(function () {
    "use strict";
    if (window.parent === window || window.shredBridgeInstalled) return;
    try {
        if (window.parent.location.origin !== location.origin || !window.parent.ShredNavigation) return;
    } catch (_) { return; }
    window.shredBridgeInstalled = true;
    const replace = history.replaceState.bind(history);
    function send(action) {
        window.parent.postMessage({ type: "shreddeals:skate-url", href: location.href, action, state: history.state }, location.origin);
    }
    // One history owner: use replace inside the iframe, and mirror pushes once
    // in the shell so Back does not encounter duplicate parent/iframe entries.
    history.pushState = function (state, title, url) { replace(state, title, url); send("push"); };
    history.replaceState = function (state, title, url) { replace(state, title, url); send("replace"); };
    history.back = function () { window.parent.postMessage({ type: "shreddeals:back" }, location.origin); };
    window.addEventListener("hashchange", () => send("replace"));
    if (document.readyState === "loading") window.addEventListener("DOMContentLoaded", () => send("replace"));
    else send("replace");
    window.addEventListener("message", event => {
        if (event.source !== window.parent || event.origin !== location.origin || !event.data || event.data.type !== "shreddeals:restore") return;
        try {
            const target = new URL(event.data.href);
            if (target.origin !== location.origin || target.pathname !== location.pathname) return;
            replace(event.data.state, "", target);
            window.dispatchEvent(new PopStateEvent("popstate", { state: event.data.state }));
        } catch (_) { /* Never follow an untrusted navigation target. */ }
    });
})();

// A single visible header for the shell. Forward to the catalog's original
// controls so section state, subscriptions and handlers stay catalog-owned.
(function () {
    'use strict';
    if (!window.shredBridgeInstalled) return;
    function mountHeader() {
        const parent = window.parent.document;
        const host = parent.querySelector('.top-row');
        const links = document.querySelector('.topnav-links');
        if (!host || !links) return;
        // Publication owns enabled scopes; rebuilt Deals pages need no injected markup.
        const app = window.parent.shredApp;
        const config = JSON.parse(parent.getElementById('sportConfig').textContent);
        const scope = (config.exploreScopes || []).find(item => item.sport === app?.state().sport.id);
        if (scope && !links.querySelector('#navExplore')) {
            const button = document.createElement('button');
            button.id = 'navExplore'; button.type = 'button'; button.textContent = 'Explore';
            button.onclick = () => app.chooseView(scope.id);
            links.appendChild(button);
        }
        parent.querySelector('.catalog-sections')?.remove();
        const nav = parent.createElement('nav');
        nav.className = 'catalog-sections';
        nav.setAttribute('aria-label', 'Catalog sections');
        const sources = new Map();
        function sync() {
            links.querySelectorAll('button[id]').forEach(source => {
                let button = sources.get(source.id);
                if (!button) {
                    button = parent.createElement('button');
                    button.type = 'button';
                    button.dataset.catalogControl = source.id;
                    button.addEventListener('click', () => {
                        if (parent.getElementById('skateFrame').hidden) return;
                        source.click();
                    });
                    sources.set(source.id, button);
                    nav.appendChild(button);
                }
                button.textContent = source.textContent;
                button.disabled = source.disabled || parent.getElementById('skateFrame').hidden;
                for (const name of ['aria-pressed', 'aria-expanded', 'aria-current', 'aria-label', 'title']) {
                    if (source.hasAttribute(name)) button.setAttribute(name, source.getAttribute(name));
                    else button.removeAttribute(name);
                }
            });
        }
        host.appendChild(nav);
        const sourceObserver = new MutationObserver(sync);
        sourceObserver.observe(links, {subtree:true, childList:true, attributes:true, characterData:true});
        const frameObserver = new MutationObserver(sync);
        frameObserver.observe(parent.getElementById('skateFrame'), {attributes:true, attributeFilter:['hidden']});
        // Scan provenance remains visible beside the result count; the mobile
        // Filters button stays in the catalog so its existing drawer still works.
        const tools = document.querySelector('.tool-display');
        const counts = document.querySelector('.tool-deals');
        const scan = document.querySelector('.scan-wrap');
        const freshness = document.querySelector('.fresh-note');
        const filters = document.getElementById('filtersOpen');
        if (counts && scan) counts.appendChild(scan);
        if (counts && freshness) counts.appendChild(freshness);
        if (tools && filters) tools.appendChild(filters);
        document.documentElement.classList.add('shred-embedded');
        sync();
        window.dispatchEvent(new Event('resize'));
        window.addEventListener('pagehide', () => {
            sourceObserver.disconnect();
            frameObserver.disconnect();
            nav.remove();
        }, {once:true});
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountHeader);
    else mountHeader();
})();

// Keep the outer header search linked to the catalog's existing search logic.
// The catalog owns filtering; we never duplicate its filter implementation.
(function () {
    "use strict";
    if (!window.shredBridgeInstalled) return;
    function wireSearch() {
        const input = document.getElementById("searchInput");
        if (!input) return;
        window.addEventListener("message", event => {
            if (event.source !== window.parent || event.origin !== location.origin ||
                event.data?.type !== "shreddeals:search-query" || typeof event.data.query !== "string") return;
            if (input.value === event.data.query) return;
            input.value = event.data.query;
            input.dispatchEvent(new Event("input", { bubbles:true }));
        });
        input.addEventListener("input", () => {
            window.parent.postMessage({type:"shreddeals:search-sync", query:input.value}, location.origin);
        });
        window.parent.postMessage({type:"shreddeals:search-sync", query:input.value}, location.origin);
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wireSearch);
    else wireSearch();
})();
