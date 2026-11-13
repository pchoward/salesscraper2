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

// Active catalog owns filtering, counts and history. The shell only mirrors it.
(function () {
    if (!window.shredBridgeInstalled) return;
    const catalogDocument = document;
    let mounted = false;
    function mountCategories() {
        if (window.document !== catalogDocument) return;
        const source = catalogDocument.getElementById('partFilters');
        const app = window.parent.shredApp;
        if (!source || !app || app.state().scope) return;
        if (!app.registerCategories(source,window,catalogDocument)) return;
        source.hidden = true; source.style.display = 'none';
        if (!mounted) {
            mounted = true;
            catalogDocument.addEventListener('pointerdown',()=>window.parent.shredApp.closeCategories());
        }
    }
    catalogDocument.addEventListener('shreddeals:catalog-ready',mountCategories);
    window.addEventListener('load',mountCategories,{once:true});
    if (catalogDocument.readyState === 'loading') catalogDocument.addEventListener('DOMContentLoaded',mountCategories,{once:true});
    else mountCategories();
})();

// Personal controls remain catalog-owned and retain their original storage format.
(function(){
    if(!window.shredBridgeInstalled)return;
    function mount(){
        const tools=document.getElementById('personalTools');
        if(!tools)return; // Explore does not expose catalog personal tools.
        tools.remove();tools.hidden=true;tools.style.display='none';document.body.appendChild(tools);
        const config=JSON.parse(window.parent.document.getElementById('sportConfig').textContent);
        const sport=config.sports.find(item=>new URL(item.catalog,window.parent.location.href).pathname===location.pathname);
        if(!sport)return;
        function views(){
            const presets=(catalog().views||[]).filter(view=>{
                const params=new URLSearchParams(view.query);
                const part=params.get('type'),store=params.get('store');
                if(part&&![...document.getElementById('partSelect').options].some(option=>option.value===slugType(part)))return false;
                if(store&&![...document.getElementById('storeSelect').options].some(option=>storeSlug(option.value)===store))return false;
                return true;
            });
            return [...presets.map(view=>({...view,builtin:true})),...customViews().map(view=>({...view,builtin:false}))]
                .map(view=>({...view,sport:view.sport||new URLSearchParams(view.query).get('sport')||null}))
                .filter(view=>view.builtin||!view.sport||view.sport===sport.id);
        }
        function sync(){
            window.parent.postMessage({type:'shreddeals:my-stuff',href:location.href,sportLabel:sport.label,
                views:views(),stars:readJson(STAR_KEY,[]).length,watching:!!state.watching,
                matching:document.querySelectorAll('.deal-row:not(.filtered-out)').length},location.origin);
        }
        const observer=new MutationObserver(sync);observer.observe(tools,{subtree:true,childList:true,attributes:true});
        const count=document.getElementById('statusCounts');if(count)observer.observe(count,{subtree:true,childList:true,characterData:true});
        const receive=event=>{
            if(event.origin!==location.origin||event.source!==window.parent||event.data?.catalog!==location.pathname)return;
            const data=event.data,name=typeof data.name==='string'?data.name.trim().slice(0,80):'';
            if(data.type==='shreddeals:save-view'&&name)saveCurrentView(name);
            else if(data.type==='shreddeals:apply-view'&&typeof data.query==='string'&&views().some(view=>view.query===data.query))applySnapshot(decodeQuery(data.query));
            else if(data.type==='shreddeals:rename-view'&&name&&customViews().some(view=>view.id===data.id))commitRename(data.id,name);
            else if(data.type==='shreddeals:delete-view'&&customViews().some(view=>view.id===data.id))deleteView(data.id);
            else if(data.type==='shreddeals:toggle-watching')toggleWatching();
            else return;
            sync();
        };
        window.addEventListener('message',receive);window.addEventListener('storage',sync);
        sync();window.addEventListener('pagehide',()=>{observer.disconnect();window.removeEventListener('message',receive);window.removeEventListener('storage',sync);},{once:true});
    }
    if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
