(function (root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    root.ShredNavigation = api;
    if (root.document) {
        const start = () => { root.shredApp = api.mount(root, JSON.parse(root.document.getElementById("sportConfig").textContent)); };
        if (root.document.readyState === "loading") root.document.addEventListener("DOMContentLoaded", start);
        else start();
    }
})(typeof window !== "undefined" ? window : globalThis, function () {
    "use strict";
    const NAV_KEYS = ["sport", "discipline", "view", "scope"];
    function state(url, config) {
        const parsed = new URL(url);
        const sport = config.sports.find(item => item.id === parsed.searchParams.get("sport")) || config.sports.find(item => item.id === config.defaultSport);
        const scope = (config.exploreScopes || []).find(item => item.sport === sport.id && item.id === parsed.searchParams.get("scope"));
        return { sport, scope: parsed.searchParams.get("view") === "explore" ? scope : null };
    }
    function clearCatalogQuery(params, config) {
        const keys = new Set(config.skateQueryKeys || []);
        // Technical URL parameters use each configured sport's namespace.
        // Do not serialize field names into index.html: another sport can add
        // a facet without making the checked-in shell stale after a merge.
        const prefixes = config.sports.map(sport => sport.id + "_");
        Array.from(params.keys()).forEach(key => {
            if (key.startsWith("ex_") || keys.has(key) || prefixes.some(prefix => key.startsWith(prefix))) params.delete(key);
        });
    }
    function navigate(url, config, sportId) {
        const next = new URL(url);
        const sport = config.sports.find(item => item.id === sportId) || config.sports.find(item => item.id === config.defaultSport);
        // Filters belong to one catalog: moving to another sport's catalog
        // starts fresh. A "coming soon" sport keeps them for the way back.
        const current = state(url, config).sport;
        if ((current.id !== sport.id || state(url, config).scope) && hasCatalog(current) && hasCatalog(sport)) clearCatalogQuery(next.searchParams, config);
        next.searchParams.set("sport", sport.id);
        next.searchParams.delete("discipline");
        next.searchParams.delete("view");
        next.searchParams.delete("scope");
        return next;
    }
    // A sport with a catalog page shows it in the frame; the rest say "coming soon".
    function catalogURL(url, config, sportId) {
        const parent = new URL(url);
        const sport = config.sports.find(item => item.id === sportId);
        const selected = state(url, config);
        const next = new URL(selected.scope && selected.sport.id === sportId ? selected.scope.catalog : sport.catalog, parent);
        next.search = parent.search;
        NAV_KEYS.forEach(key => next.searchParams.delete(key));
        next.hash = parent.hash;
        return next;
    }
    function skateURL(url, config) { return catalogURL(url, config, "skate"); }
    function hasCatalog(sport) { return !!(sport && sport.catalog); }
    function mergeSkateURL(parentURL, childURL, config, sportId) {
        const parent = new URL(parentURL);
        const child = new URL(childURL);
        const expected = catalogURL(parentURL, config, sportId || "skate");
        if (child.origin !== parent.origin || child.pathname !== expected.pathname) throw new Error("Unexpected child URL");
        // Remove only production-owned keys. Unknown legacy/analytics parameters
        // survive even when the embedded app's normalizer does not know them.
        clearCatalogQuery(parent.searchParams, config);
        const incomingKeys = new Set(child.searchParams.keys());
        incomingKeys.forEach(key => { if (!NAV_KEYS.includes(key)) parent.searchParams.delete(key); });
        child.searchParams.forEach((value, key) => { if (!NAV_KEYS.includes(key)) parent.searchParams.append(key, value); });
        parent.searchParams.delete("discipline");
        parent.hash = child.hash;
        return parent;
    }
    function nextIndex(index, key, length) {
        if (key === "Home") return 0;
        if (key === "End") return length - 1;
        if (key === "ArrowRight") return (index + 1) % length;
        if (key === "ArrowLeft") return (index - 1 + length) % length;
        return null;
    }
    function mount(win, config) {
        const cleanURL = new URL(win.location.href);
        if (cleanURL.searchParams.has("discipline")) {
            cleanURL.searchParams.delete("discipline");
            win.history.replaceState(win.history.state, "", cleanURL);
        }
        const doc = win.document;
        const sportTabs = doc.getElementById("sportTabs");
        const frame = doc.getElementById("skateFrame");
        const empty = doc.getElementById("comingSoon");
        const brand = doc.getElementById("brandHome");
        const shellSearch = doc.getElementById("shellSearch");
        const stuffPanel = doc.getElementById('myStuffPanel');
        const stuffToggle = doc.getElementById('myStuffToggle');
        const stuffName = doc.getElementById('myStuffName');
        let stuffReady = false, stuffReturnTabIndex = null;
        function closeMyStuff(focus=false) {
            if (stuffPanel.hidden) return;
            stuffPanel.hidden = true;
            stuffToggle.setAttribute('aria-expanded','false');
            doc.getElementById('myStuffBackdrop').hidden = true;
            doc.body.classList.remove('my-stuff-open');
            frame.inert = false;
            if (stuffReturnTabIndex == null) frame.removeAttribute('tabindex');
            else frame.setAttribute('tabindex',stuffReturnTabIndex);
            if(focus)stuffToggle.focus({preventScroll:true});
        }
        function sendStuff(type,extra={}) {
            if(!stuffReady || frame.hidden)return;
            const current = state(win.location.href,config);
            frame.contentWindow.postMessage({type,...extra,catalog:catalogURL(win.location.href,config,current.sport.id).pathname},win.location.origin);
        }
        stuffToggle.addEventListener('click',()=>{
            if(!stuffPanel.hidden){closeMyStuff(true);return;}
            closeCategories();
            stuffPanel.hidden=false;stuffToggle.setAttribute('aria-expanded','true');
            doc.getElementById('myStuffBackdrop').hidden=false;
            doc.body.classList.add('my-stuff-open');
            stuffReturnTabIndex=frame.getAttribute('tabindex');frame.inert=true;frame.tabIndex=-1;
            doc.getElementById('myStuffClose').focus({preventScroll:true});
        });
        doc.getElementById('myStuffClose').addEventListener('click',()=>closeMyStuff(true));
        doc.getElementById('myStuffBackdrop').addEventListener('click',()=>closeMyStuff(true));
        doc.addEventListener('keydown',event=>{
            if(stuffPanel.hidden)return;
            if(event.key==='/'&&!event.target.closest('input,textarea,select'))closeMyStuff();
            if(event.key==='Escape'){event.preventDefault();event.stopPropagation();closeMyStuff(true);}
            if(event.key==='Tab'){
                const stops=[...stuffPanel.querySelectorAll('button,input')].filter(node=>!node.disabled&&!node.hidden);
                const first=stops[0],last=stops[stops.length-1];
                if(event.shiftKey&&doc.activeElement===first){event.preventDefault();last?.focus();}
                else if(!event.shiftKey&&doc.activeElement===last){event.preventDefault();first?.focus();}
            }
        });
        function clearRename(){delete stuffName.dataset.rename;stuffName.value='';doc.getElementById('myStuffSave').textContent='Save current view';doc.getElementById('myStuffCancel').hidden=true;}
        doc.getElementById('myStuffCancel').addEventListener('click',clearRename);
        doc.getElementById('myStuffSaveForm').addEventListener('submit',event=>{
            event.preventDefault();const name=stuffName.value.trim();if(!name)return;
            sendStuff(stuffName.dataset.rename?'shreddeals:rename-view':'shreddeals:save-view',{name,id:stuffName.dataset.rename});
            clearRename();doc.getElementById('myStuffStatus').textContent='View saved.';
        });
        doc.getElementById('myStuffWatching').addEventListener('click',()=>sendStuff('shreddeals:toggle-watching'));
        doc.getElementById('myStuffBookmark').addEventListener('click',async()=>{
            let href=win.location.href;
            try {
                const child=frame.contentWindow;
                if(stuffReady&&typeof child.currentQuery==='function'){
                    const source=new URL(child.location.href);source.search=child.currentQuery();
                    href=mergeSkateURL(href,source,config,state(href,config).sport.id).href;
                }
                await win.navigator.clipboard.writeText(href);
                doc.getElementById('myStuffStatus').textContent='Selection link copied.';
            } catch(_){const input=doc.getElementById('myStuffCopyFallback');input.hidden=false;input.value=href;input.focus();input.select();doc.getElementById('myStuffStatus').textContent='Copy this selection link.';}
        });
        function renderStuff(data) {
            stuffReady=true;doc.getElementById('myStuffSave').disabled=false;
            const watching=doc.getElementById('myStuffWatching');watching.disabled=false;watching.setAttribute('aria-pressed',String(!!data.watching));watching.textContent=data.watching?'Show all deals':'Show watching';
            doc.getElementById('myStuffStars').textContent=data.stars+' starred deal'+(data.stars===1?'':'s')+' · '+data.matching+' matching this selection';
            if(doc.getElementById('myStuffStatus').textContent==='Loading catalog tools…')doc.getElementById('myStuffStatus').textContent='';
            const focused=doc.activeElement?.dataset?.viewKey;
            const list=doc.getElementById('myStuffViews');list.replaceChildren();
            for(const view of data.views||[]) {
                const row=doc.createElement('div');row.className='my-stuff-view';
                const apply=doc.createElement('button');apply.type='button';apply.className='apply-view';apply.textContent=view.name+(view.builtin?' · '+data.sportLabel:view.sport?' · '+(config.sports.find(sport=>sport.id===view.sport)?.label||view.sport):' · Shared');apply.dataset.viewKey='apply-'+view.id;
                apply.addEventListener('click',()=>{sendStuff('shreddeals:apply-view',{query:view.query});closeMyStuff(true);});row.appendChild(apply);
                if(!view.builtin){
                    const rename=doc.createElement('button');rename.type='button';rename.textContent='Rename';rename.dataset.viewKey='rename-'+view.id;rename.setAttribute('aria-label','Rename '+view.name);
                    rename.addEventListener('click',()=>{stuffName.value=view.name;stuffName.dataset.rename=view.id;doc.getElementById('myStuffSave').textContent='Rename view';doc.getElementById('myStuffCancel').hidden=false;stuffName.focus();});
                    const remove=doc.createElement('button');remove.type='button';remove.textContent='×';remove.dataset.viewKey='delete-'+view.id;remove.setAttribute('aria-label','Delete '+view.name);remove.addEventListener('click',()=>sendStuff('shreddeals:delete-view',{id:view.id}));row.append(rename,remove);
                }
                list.appendChild(row);
            }
            if(focused&&!stuffPanel.hidden)list.querySelector('[data-view-key='+JSON.stringify(focused)+']')?.focus({preventScroll:true});
        }
        function syncSearch(url) {
            const current = state(url, config);
            const params = new URL(url).searchParams;
            shellSearch.value = hasCatalog(current.sport) ? params.get(current.scope ? 'ex_query' : 'q') || '' : '';
            shellSearch.disabled = !hasCatalog(current.sport);
        }
        function sendSearch() {
            if (frame.hidden || !frame.contentWindow) return;
            frame.contentWindow.postMessage({ type:"shreddeals:search-query", query:shellSearch.value }, win.location.origin);
        }
        shellSearch.addEventListener("input", sendSearch);
        function searchEvent(type, extra={}) {
            if (!frame.hidden) frame.contentWindow.postMessage({type,...extra},win.location.origin);
        }
        shellSearch.addEventListener('focus', () => searchEvent('shreddeals:search-focus',{focused:true}));
        shellSearch.addEventListener('blur', () => {
            doc.getElementById('shellSuggestions').hidden = true;
            shellSearch.setAttribute('aria-expanded','false');
            searchEvent('shreddeals:search-focus',{focused:false});
        });
        shellSearch.addEventListener('keydown', event => {
            if (!['ArrowDown','ArrowUp','Enter','Escape'].includes(event.key)) return;
            event.preventDefault(); searchEvent('shreddeals:search-key',{key:event.key});
        });
        doc.addEventListener("keydown", event => {
            if (event.key !== "/" || event.ctrlKey || event.altKey || event.metaKey) return;
            const t = event.target;
            if (t && (t.closest("input,textarea,select") || t.isContentEditable)) return;
            event.preventDefault(); shellSearch.focus();
        });
        brand.textContent = config.brand.name;
        brand.title = config.brand.domain || "Back to Skate";
        const panel = doc.getElementById('categoryPanel');
        const choices = doc.getElementById('categoryChoices');
        const sources = new Map();
        let menuSport = null, opener = null, dismissTimer;
        const categoryLoads = new Map(), categoryErrors = new Set(), categoryCache = new Map();
        let suppressFocus = false, hoverBlockPoint = null, pendingMenuFocus = null;
        function closeCategories(focus=false) {
            win.clearTimeout(dismissTimer);
            panel.hidden = true; pendingMenuFocus = null;
            sportTabs.querySelectorAll('button').forEach(button => button.setAttribute('aria-expanded','false'));
            doc.getElementById('categoryToggle').setAttribute('aria-expanded','false');
            if (focus && opener?.isConnected) {
                suppressFocus = true; opener.focus({preventScroll:true}); suppressFocus = false;
            }
        }
        function fitCategories() {
            if (panel.hidden) return;
            const height = win.visualViewport?.height || win.innerHeight;
            panel.style.maxHeight = Math.max(0,Math.min(460,height-panel.getBoundingClientRect().top-12)) + 'px';
        }
        win.addEventListener('resize',fitCategories);
        win.visualViewport?.addEventListener('resize',fitCategories);
        function refreshCategories() {
            const entry = sources.get(menuSport);
            choices.replaceChildren();
            const sport = config.sports.find(item => item.id === menuSport);
            doc.getElementById('categoryTitle').textContent = (sport?.label || '') + ' categories';
            panel.setAttribute('aria-busy',String(!entry));
            doc.getElementById('categoryHint').textContent = entry ?
                (menuSport === state(win.location.href,config).sport.id ? 'Counts update with your filters.' : 'Counts for this sport before applying filters.') : 'Loading catalog categories…';
            if (!entry) {
                if (categoryErrors.has(menuSport)) {
                    panel.setAttribute('aria-busy','false');
                    doc.getElementById('categoryHint').textContent = 'Categories could not load. Reopen this menu to retry.';
                }
                return;
            }
            const originals = entry.source ? [...entry.source.querySelectorAll('button[data-part]')].sort((a,b)=>Number(a.dataset.order)-Number(b.dataset.order)) : entry.categories;
            for (const original of originals) {
                const part = entry.source ? original.dataset.part : original.category;
                const button = doc.createElement('button');
                button.type = 'button'; button.className = 'category-choice'; button.dataset.part = part;
                const name = part === 'all' ? 'All products' : entry.source ? original.querySelector('.quick-name').textContent : (original.label || part);
                const count = entry.source ? original.getAttribute('data-count') || '0' : String(original.count);
                const active = !!entry.source && menuSport === state(win.location.href,config).sport.id && original.getAttribute('aria-pressed') === 'true';
                for (const [className,text] of [['category-name',name],['category-count',count]]) {
                    const span = doc.createElement('span'); span.className = className; span.textContent = text; button.appendChild(span);
                }
                button.dataset.count = count;
                button.setAttribute('aria-pressed',String(active));
                button.disabled = (entry.source && original.disabled) || (Number(count) === 0 && !active && part !== 'all');
                button.setAttribute('aria-label',name + ', ' + count + ' matching products');
                button.addEventListener('click',() => {
                    const current = state(win.location.href,config);
                    if (menuSport === current.sport.id && !current.scope && entry.child === frame.contentWindow) original.click();
                    else {
                        const next = navigate(win.location.href,config,menuSport);
                        if (part === 'all') next.searchParams.set('type','all');
                        else next.searchParams.set('type',entry.source ? entry.child.typeSlug(part) : original.slug);
                        win.history.pushState({},'',next); render();
                    }
                    opener = doc.getElementById('sport-'+state(win.location.href,config).sport.id);
                    closeCategories(true);
                });
                choices.appendChild(button);
            }
            if (pendingMenuFocus === menuSport && doc.activeElement === opener) {
                pendingMenuFocus = null; choices.querySelector('button:not(:disabled)')?.focus();
            }
        }
        function registerCategories(source,child) {
            const sport = config.sports.find(item => new URL(item.catalog,win.location.href).pathname === child.location.pathname);
            if (!sport) return;
            const entry = {source,child}; sources.set(sport.id,entry);
            function sync() {
                if (sources.get(sport.id) !== entry) return;
                if (menuSport === sport.id && !panel.hidden) {
                    // Preserve keyboard focus when counts change in the open menu.
                    const focused = choices.contains(doc.activeElement) ? doc.activeElement.dataset.part : null;
                    refreshCategories();
                    if (focused) choices.querySelector('[data-part='+JSON.stringify(focused)+']')?.focus({preventScroll:true});
                }
                if (state(win.location.href,config).sport.id !== sport.id || state(win.location.href,config).scope) return;
                const selected = source.querySelector('[aria-pressed=true]');
                const parts = typeof child.typedFilters === 'function' ? child.typedFilters(child.document.getElementById('searchInput')?.value || '').parts : null;
                const searching = parts?.length && (parts.length !== 1 || parts[0] !== selected?.dataset.part);
                const label = searching ? 'Search results' : selected?.dataset.part === 'all' ? 'All products' : selected?.querySelector('.quick-name')?.textContent || 'Categories';
                doc.getElementById('categoryLabel').textContent = label;
                doc.getElementById('categoryCount').textContent = /^\s*([\d,]+)/.exec(child.document.getElementById('statusCounts')?.textContent || '')?.[1] || '0';
                const toggle = doc.getElementById('categoryToggle');
                toggle.disabled = false; toggle.setAttribute('aria-label',sport.label + ': ' + label + '. Choose product category');
                doc.getElementById('categoryNavigation').hidden = false;
                if (panel.hidden && (menuSport === sport.id || !menuSport)) { menuSport = sport.id; refreshCategories(); }
            }
            const observer = new MutationObserver(sync);
            observer.observe(source,{childList:true,subtree:true,attributes:true,characterData:true});
            const status = child.document.getElementById('statusCounts');
            if (status) observer.observe(status,{childList:true,subtree:true,characterData:true});
            child.addEventListener('pagehide',()=>{
                observer.disconnect();
                if(sources.get(sport.id)===entry) {
                    if(categoryCache.has(sport.id))sources.set(sport.id,{categories:categoryCache.get(sport.id)});
                    else sources.delete(sport.id);
                }
            },{once:true});
            sync();
        }
        function openSportMenu(id,button) {
            win.clearTimeout(dismissTimer);
            menuSport = id; opener = button; panel.hidden = false;
            sportTabs.querySelectorAll('button').forEach(node=>node.setAttribute('aria-expanded',String(node === button)));
            doc.getElementById('categoryToggle').setAttribute('aria-expanded',String(button.id === 'categoryToggle'));
            const sport = config.sports.find(item=>item.id===id);
            const current = state(win.location.href,config);
            // A departing catalog can still be unloading. Never show its
            // filtered live counts as another sport's unfiltered totals.
            if (sources.get(id)?.source && (current.sport.id !== id || current.scope)) {
                if (categoryCache.has(id)) sources.set(id,{categories:categoryCache.get(id)});
                else sources.delete(id);
            }
            if (hasCatalog(sport) && !sources.has(id) && !categoryLoads.has(id)) {
                categoryErrors.delete(id);
                const load = win.fetch(sport.categoriesURL).then(response=>{
                    if (!response.ok) throw new Error('Category metadata unavailable');
                    return response.json();
                }).then(categories=>{
                    if (!Array.isArray(categories) || !categories.every(item=>typeof item.category==='string' && typeof item.slug==='string' && Number.isInteger(item.order) && Number.isInteger(item.count) && item.count>=0)) throw new Error('Invalid category metadata');
                    categoryCache.set(id,categories);
                    // A catalog may have become active while the request ran.
                    if (!sources.get(id)?.source) sources.set(id,{categories:categories.sort((a,b)=>a.order-b.order)});
                }).catch(()=>categoryErrors.add(id)).finally(()=>{
                    categoryLoads.delete(id);
                    if(menuSport===id && !panel.hidden) {refreshCategories();fitCategories();}
                });
                categoryLoads.set(id,load);
            }
            refreshCategories(); fitCategories();
            if (!hasCatalog(config.sports.find(item=>item.id===id))) {
                panel.setAttribute('aria-busy','false');
                doc.getElementById('categoryHint').textContent = 'No catalog available for this sport yet.';
            }
        }
        const region = doc.querySelector('.browse-nav');
        region.addEventListener('pointerenter',()=>win.clearTimeout(dismissTimer));
        doc.addEventListener('pointermove',event=>{
            if (!hoverBlockPoint || event.pointerType === 'touch' || Math.hypot(event.clientX-hoverBlockPoint.x,event.clientY-hoverBlockPoint.y)<3) return;
            hoverBlockPoint = null;
            const button = event.target.closest('#sportTabs button');
            if (button) openSportMenu(button.id.slice(6),button);
        });
        region.addEventListener('pointerleave',event=>{
            if (event.pointerType !== 'touch') dismissTimer = win.setTimeout(()=>closeCategories(),180);
        });
        doc.getElementById('categoryToggle').addEventListener('click',event=> {
            if (!panel.hidden) closeCategories(); else openSportMenu(state(win.location.href,config).sport.id,event.currentTarget);
        });
        doc.getElementById('categoryClose').addEventListener('click',()=>closeCategories(true));
        doc.addEventListener('pointerdown',event=>{if(!event.target.closest('.browse-nav'))closeCategories();});
        doc.addEventListener('focusin',event=>{if(!event.target.closest('.browse-nav'))closeCategories();});
        doc.addEventListener('keydown',event=>{if(event.key==='Escape'&&!panel.hidden){event.preventDefault();closeCategories(true);}});
        region.addEventListener('keydown',event=>{
            if (event.key !== 'ArrowDown' || choices.contains(event.target)) return;
            event.preventDefault();
            const id = event.target.id.startsWith('sport-') ? event.target.id.slice(6) : state(win.location.href,config).sport.id;
            openSportMenu(id,event.target);
            const first = choices.querySelector('button:not(:disabled)');
            if (first) first.focus(); else pendingMenuFocus = id;
        });
        choices.addEventListener('keydown',event=>{
            const buttons = [...choices.querySelectorAll('button:not(:disabled)')];
            const index = buttons.indexOf(doc.activeElement);
            const key = event.key==='ArrowDown'?'ArrowRight':event.key==='ArrowUp'?'ArrowLeft':event.key;
            const next = nextIndex(index,key,buttons.length);
            if(next==null||!buttons.length)return;
            event.preventDefault();buttons[next].focus();
        });
        function choose(sportId, focusGroup) {
            const next = navigate(win.location.href, config, sportId);
            if (next.href !== win.location.href) win.history.pushState(win.history.state || {}, "", next);
            render(focusGroup);
        }
        function chooseView(scopeId) {
            const next = new URL(win.location.href);
            const current = state(next, config);
            const scope = (config.exploreScopes || []).find(item => item.id === scopeId && item.sport === current.sport.id);
            clearCatalogQuery(next.searchParams, config);
            next.hash = "";
            next.searchParams.delete("view");
            next.searchParams.delete("scope");
            if (scope) { next.searchParams.set("view", "explore"); next.searchParams.set("scope", scope.id); }
            win.history.pushState({}, "", next);
            render();
        }
        function tabs(container, items, selected, prefix, panel, chooseItem) {
            if (items.every(item => doc.getElementById(prefix+item.id))) {
                items.forEach(item => {
                    const button = doc.getElementById(prefix+item.id);
                    button.setAttribute('aria-selected',String(item.id===selected));
                    button.tabIndex = item.id===selected ? 0 : -1;
                });
                return;
            }
            container.replaceChildren(...items.map(item => {
                const button = doc.createElement("button");
                button.type = "button";
                button.id = prefix + item.id;
                button.setAttribute("role", "tab");
                button.setAttribute("aria-selected", String(item.id === selected));
                button.setAttribute("aria-controls", panel);
                button.tabIndex = item.id === selected ? 0 : -1;
                button.textContent = item.label;
                button.setAttribute('aria-haspopup','true');
                button.setAttribute('aria-expanded','false');
                button.setAttribute('aria-controls','categoryPanel sportPanel');
                button.addEventListener('pointerenter',event=>{if(event.pointerType !== 'touch' && !hoverBlockPoint)openSportMenu(item.id,button);});
                button.addEventListener('focus',()=>{if(!suppressFocus)openSportMenu(item.id,button);});
                let touch = false;
                button.addEventListener('pointerdown',event=>{touch = event.pointerType === 'touch';});
                button.addEventListener("click", event => {
                    if(touch){touch=false;openSportMenu(item.id,button);return;}
                    hoverBlockPoint = {x:event.clientX,y:event.clientY};
                    const next = navigate(win.location.href,config,item.id);
                    clearCatalogQuery(next.searchParams,config);
                    next.searchParams.delete('type');
                    next.searchParams.set('type','all');
                    win.history.pushState({},'',next);render();closeCategories();
                });
                button.addEventListener("keydown", event => {
                    const index = nextIndex(items.findIndex(value => value.id === item.id), event.key, items.length);
                    if (index == null) return;
                    event.preventDefault();
                    doc.getElementById(prefix+items[index].id).focus();
                });
                return button;
            }));
        }
        function restoreFrame(historyState) {
            const sport = state(win.location.href, config).sport;
            if (!hasCatalog(sport) || !frame.dataset.ready) return;
            const expected = catalogURL(win.location.href, config, sport.id);
            if (frame.dataset.currentURL !== expected.href) return;
            frame.contentWindow.postMessage({ type: "shreddeals:restore", href: expected.href, state: historyState && historyState.skateState || null }, win.location.origin);
        }
        function render(focusGroup) {
            closeMyStuff();stuffReady=false;clearRename();
            doc.getElementById('myStuffViews').replaceChildren();
            doc.getElementById('myStuffSave').disabled=true;doc.getElementById('myStuffWatching').disabled=true;
            doc.getElementById('myStuffStars').textContent='';doc.getElementById('myStuffStatus').textContent='Loading catalog tools…';
            const current = state(win.location.href, config);
            if(current.scope || !hasCatalog(current.sport))doc.getElementById('myStuffStatus').textContent='Personal tools are available in Deals. You can still bookmark this selection.';
            closeCategories();
            menuSport = current.sport.id;
            const categories = doc.getElementById('categoryNavigation');
            categories.hidden = true;
            doc.getElementById('categoryToggle').disabled = true;
            syncSearch(win.location.href);
            const unchangedCatalog = hasCatalog(current.sport) && frame.dataset.currentURL === catalogURL(win.location.href,config,current.sport.id).href;
            if (!unchangedCatalog) doc.getElementById('categoryChoices').replaceChildren();
            if (unchangedCatalog && !current.scope && doc.querySelector('#categoryChoices button')) {
                categories.hidden = false;
                doc.getElementById('categoryToggle').disabled = false;
            }
            tabs(sportTabs, config.sports, current.sport.id, "sport-", "sportPanel", id => choose(id, "sport"));
            doc.getElementById("sportPanel").setAttribute("aria-labelledby", "sport-" + current.sport.id);
            doc.title = config.brand.name + " · " + current.sport.label + (config.production ? "" : " preview");
            const skate = hasCatalog(current.sport);
            frame.hidden = !skate;
            frame.setAttribute("aria-hidden", String(!skate));
            frame.tabIndex = skate ? 0 : -1;
            empty.hidden = skate;
            const note = doc.getElementById("contextNote");
            note.hidden = !!config.production;
            if (skate) {
                note.textContent = config.production ? "" : (current.sport.id === "skate" ? "Skate · saved SkateDeals catalog" : current.sport.label + " · preview catalog") + ". Development preview; live delivery is disabled.";
                const target = catalogURL(win.location.href, config, current.sport.id).href;
                if (frame.dataset.currentURL !== target) {
                    delete frame.dataset.ready;
                    const loaded = frame.dataset.currentURL;
                    frame.dataset.currentURL = target;
                    // Swapping catalogs (Skate to BMX) must not add a history
                    // entry of its own, or Back would only change the frame.
                    let replaced = false;
                    if (loaded) {
                        try { frame.contentWindow.location.replace(target); replaced = true; } catch (_) { /* not loaded yet */ }
                    }
                    if (!replaced) frame.src = target;
                }
            } else {
                note.textContent = config.production ? "" : current.sport.label + " · navigation prototype";
                doc.getElementById("emptyTitle").textContent = current.sport.label;
                doc.getElementById("emptyDescription").textContent = config.production ? "Explore Skate deals while we add " + current.sport.label + " deals." : "Inventory for " + current.sport.label + " has not been connected.";
            }
            if (focusGroup) {
                const target = doc.getElementById("sport-" + current.sport.id);
                suppressFocus = true; target.focus({ preventScroll: true }); suppressFocus = false;
                target.scrollIntoView({ block: "nearest", inline: "nearest" });
            }
        }
        win.addEventListener("popstate", event => { render(); restoreFrame(event.state); });
        win.addEventListener("message", event => {
            if (event.origin !== win.location.origin || event.source !== frame.contentWindow || !event.data) return;
            const current = state(win.location.href, config).sport;
            const currentSport = current.id;
            if(event.data.type==='shreddeals:my-stuff'){
                try {mergeSkateURL(win.location.href,event.data.href,config,currentSport);renderStuff(event.data);}catch(_){}
                return;
            }
            if (event.data.type === "shreddeals:search-sync") {
                if (!hasCatalog(current) || typeof event.data.query !== 'string') return;
                try {
                    // Reject messages still queued from the previous sport/view.
                    mergeSkateURL(win.location.href, event.data.href, config, currentSport);
                    shellSearch.value = event.data.query;
                } catch (_) { /* Ignore a late load or foreign path. */ }
                return;
            }
            if (event.data.type === "shreddeals:back") { if (hasCatalog(current)) win.history.back(); return; }
            if (event.data.type !== "shreddeals:skate-url") return;
            try {
                if (!hasCatalog(current)) {
                    // A late load while hidden must not rewrite the active sport.
                    frame.dataset.ready = "true";
                    return;
                }
                // Throws for a late load of another sport's catalog: ignored.
                const next = mergeSkateURL(win.location.href, event.data.href, config, currentSport);
                syncSearch(next.href);
                frame.dataset.ready = "true";
                // Cache the shell's logical URL, including retained unknown keys,
                // rather than reloading whenever the embedded normalizer drops one.
                frame.dataset.currentURL = catalogURL(next, config, currentSport).href;
                const method = event.data.action === "push" ? "pushState" : "replaceState";
                win.history[method]({ skateState: event.data.state || null }, "", next);
            } catch (_) { /* Ignore foreign paths and malformed messages. */ }
        });
        brand.addEventListener("click", () => choose("skate", "sport"));
        doc.getElementById("backToSkate").addEventListener("click", () => choose("skate", "sport"));
        render();
        return { render, choose, chooseView, state: () => state(win.location.href, config), closeCategories, registerCategories, bridgeVersion: config.bridgeVersion };
    }
    return { state, navigate, skateURL, catalogURL, mergeSkateURL, nextIndex, mount };
});
