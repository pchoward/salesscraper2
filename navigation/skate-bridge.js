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
        const input = document.getElementById("searchInput") || document.getElementById("query");
        if (!input) return;
        const header = window.parent.document.getElementById('shellSearch');
        if (!header) return;
        const field = input.closest('.search-field') || (input.id === 'query' ? input.parentElement : null);
        if (field) field.hidden = true;
        const box = input.closest('.tool-search');
        if (box) box.style.display = 'contents';
        window.addEventListener("message", event => {
            if (event.source !== window.parent || event.origin !== location.origin) return;
            const data = event.data;
            if (data?.type === 'shreddeals:search-query' && typeof data.query === 'string') {
                if (input.value === data.query) return;
                input.value = data.query;
                input.dispatchEvent(new Event('input',{bubbles:true}));
            } else if (data?.type === 'shreddeals:search-key' && ['ArrowDown','ArrowUp','Enter','Escape'].includes(data.key)) {
                input.dispatchEvent(new KeyboardEvent('keydown',{key:data.key,bubbles:true,cancelable:true}));
            } else if (data?.type === 'shreddeals:search-focus' && typeof data.focused === 'boolean') {
                input.dispatchEvent(new FocusEvent(data.focused ? 'focus' : 'blur'));
            }
        });
        const list = document.getElementById('searchSuggest');
        const popup = window.parent.document.getElementById('shellSuggestions');
        if (list && popup) {
            function mirrorSuggestions() {
                const open = !list.hidden && header.ownerDocument.activeElement === header;
                popup.hidden = !open;
                header.setAttribute('aria-expanded',String(open));
                if (!open) { popup.replaceChildren(); header.removeAttribute('aria-activedescendant'); return; }
                const copies = [...list.childNodes].map(node => node.cloneNode(true));
                popup.replaceChildren(...copies);
                popup.querySelectorAll('[id]').forEach(node => { node.id = 'shell-' + node.id; });
                popup.querySelectorAll('[aria-labelledby]').forEach(node => {
                    node.setAttribute('aria-labelledby',node.getAttribute('aria-labelledby').split(' ').map(id => 'shell-' + id).join(' '));
                });
                popup.querySelectorAll('[role=option]').forEach(option => {
                    const id = option.id.slice('shell-'.length);
                    option.addEventListener('pointerdown',event => {
                        event.preventDefault();
                        document.getElementById(id)?.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true}));
                    });
                });
                const active = input.getAttribute('aria-activedescendant');
                if (active) {
                    header.setAttribute('aria-activedescendant','shell-' + active);
                    popup.querySelector('[aria-selected=true]')?.scrollIntoView({block:'nearest'});
                } else header.removeAttribute('aria-activedescendant');
            }
            const suggestions = new MutationObserver(mirrorSuggestions);
            suggestions.observe(list,{childList:true,subtree:true,attributes:true});
            suggestions.observe(input,{attributes:true,attributeFilter:['aria-expanded','aria-activedescendant']});
            window.addEventListener('pagehide',() => { suggestions.disconnect(); popup.hidden=true; },{once:true});
        }
        let lastQuery = null;
        function sync() {
            if (input.value === lastQuery) return;
            lastQuery = input.value;
            window.parent.postMessage({type:"shreddeals:search-sync", href:location.href, query:input.value}, location.origin);
        }
        input.addEventListener("input", sync);
        // Chips/saved searches/reset can change .value without an input event,
        // even before the debounced URL update commits. Observe the catalog's
        // own rendered search state; do not replace its search implementation.
        const renderedSearch = document.getElementById("searchChips") || document.getElementById("count");
        if (renderedSearch) {
            const observer = new MutationObserver(sync);
            observer.observe(renderedSearch, {childList:true, subtree:true, characterData:true});
            window.addEventListener('pagehide', () => observer.disconnect(), {once:true});
        }
        // Let the catalog's DOMContentLoaded handlers restore URL/search state first.
        setTimeout(sync, 0);
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wireSearch);
    else wireSearch();
})();

// #212: category navigation mirrors the catalog's own buttons and facet counts.
// No second category dataset, count algorithm, or filter state lives in the shell.
(function () {
    'use strict';
    if (!window.shredBridgeInstalled) return;
    function mountCategories() {
        const parent = window.parent.document;
        const source = document.getElementById('partFilters');
        const host = parent.getElementById('categoryNavigation');
        const app = window.parent.shredApp;
        if (!source || !host || !app || app.state().scope) return;
        const choices = parent.getElementById('categoryChoices');
        const toggle = parent.getElementById('categoryToggle');
        const config = JSON.parse(parent.getElementById('sportConfig').textContent);
        const ownPath = location.pathname;
        function isCurrent() {
            const current = app.state();
            return !current.scope && window.parent.ShredNavigation.catalogURL(window.parent.location.href,config,current.sport.id).pathname === ownPath;
        }
        if (!isCurrent()) return;
        source.hidden = true;
        source.style.display = 'none';
        choices.replaceChildren();
        const buttons = new Map();
        function sync() {
            if (!isCurrent()) return;
            const originals = [...source.querySelectorAll('button[data-part]')].sort((a,b) => Number(a.dataset.order)-Number(b.dataset.order));
            const present = new Set();
            let selected;
            for (const original of originals) {
                const part = original.dataset.part;
                present.add(part);
                let button = buttons.get(part);
                if (!button) {
                    button = parent.createElement('button');
                    button.type = 'button'; button.className = 'category-choice'; button.dataset.part = part;
                    const label = parent.createElement('span'); label.className = 'category-name';
                    const count = parent.createElement('span'); count.className = 'category-count';
                    button.append(label,count);
                    button.addEventListener('click',() => {
                        if (!isCurrent()) return;
                        original.click();
                        app.closeCategories(true);
                    });
                    buttons.set(part,button); choices.appendChild(button);
                }
                const name = part === 'all' ? 'All products' : original.querySelector('.quick-name').textContent;
                const count = original.getAttribute('data-count') ?? original.querySelector('.quick-count').textContent;
                const active = original.getAttribute('aria-pressed') === 'true';
                button.querySelector('.category-name').textContent = name;
                button.querySelector('.category-count').textContent = count;
                button.dataset.count = count;
                button.setAttribute('aria-pressed',String(active));
                button.disabled = original.disabled || (Number(count) === 0 && !active && part !== 'all');
                button.setAttribute('aria-label',name + ', ' + count + ' matching products');
                if (active) selected = {name,count,part};
            }
            for (const [part,button] of buttons) if (!present.has(part)) { button.remove(); buttons.delete(part); }
            const sport = app.state().sport;
            parent.getElementById('categoryTitle').textContent = sport.label + ' categories';
            const queryParts = typeof typedFilters === 'function' && typeof state !== 'undefined' ? typedFilters(state.search).parts : null;
            const searchScope = queryParts?.length && (queryParts.length !== 1 || queryParts[0] !== selected?.part);
            const label = searchScope ? 'Search results' : selected?.name || 'Categories';
            parent.getElementById('categoryLabel').textContent = label;
            const hint = parent.getElementById('categoryHint');
            if (hint) hint.textContent = searchScope ? 'Your search selects the product type. Clear it to browse another category.' : 'Counts update with your filters.';
            // The native category facet can broaden category-specific sizes.
            // Keep those menu counts; the trigger reports the actual result count.
            const matched = /^\s*([\d,]+)/.exec(document.getElementById('statusCounts')?.textContent || '')?.[1] || selected?.count || '0';
            parent.getElementById('categoryCount').textContent = matched;
            toggle.setAttribute('aria-label',sport.label + ': ' + label + ', ' + matched + ' matching products. Choose product category');
            toggle.disabled = originals.length === 0;
            host.hidden = originals.length === 0;
        }
        const observer = new MutationObserver(sync);
        observer.observe(source,{childList:true,subtree:true,attributes:true,characterData:true});
        const status = document.getElementById('statusCounts');
        if (status) observer.observe(status,{childList:true,subtree:true,characterData:true});
        const dismiss = () => app.closeCategories();
        document.addEventListener('pointerdown',dismiss);
        setTimeout(sync,0);
        window.addEventListener('pagehide',() => {
            observer.disconnect(); document.removeEventListener('pointerdown',dismiss);
            if (isCurrent()) { app.closeCategories(); host.hidden = true; toggle.disabled = true; }
        },{once:true});
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',mountCategories);
    else mountCategories();
})();
