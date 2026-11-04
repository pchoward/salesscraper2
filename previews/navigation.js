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
        doc.addEventListener("keydown", event => {
            if (event.key !== "/" || event.ctrlKey || event.altKey || event.metaKey) return;
            const t = event.target;
            if (t && (t.closest("input,textarea,select") || t.isContentEditable)) return;
            event.preventDefault(); shellSearch.focus();
        });
        brand.textContent = config.brand.name;
        brand.title = config.brand.domain || "Back to Skate";
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
            container.replaceChildren(...items.map(item => {
                const button = doc.createElement("button");
                button.type = "button";
                button.id = prefix + item.id;
                button.setAttribute("role", "tab");
                button.setAttribute("aria-selected", String(item.id === selected));
                button.setAttribute("aria-controls", panel);
                button.tabIndex = item.id === selected ? 0 : -1;
                button.textContent = item.label;
                button.addEventListener("click", () => chooseItem(item.id));
                button.addEventListener("keydown", event => {
                    const index = nextIndex(items.findIndex(value => value.id === item.id), event.key, items.length);
                    if (index == null) return;
                    event.preventDefault();
                    chooseItem(items[index].id);
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
            const current = state(win.location.href, config);
            syncSearch(win.location.href);
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
                target.focus({ preventScroll: true });
                target.scrollIntoView({ block: "nearest", inline: "nearest" });
            }
        }
        win.addEventListener("popstate", event => { render(); restoreFrame(event.state); });
        win.addEventListener("message", event => {
            if (event.origin !== win.location.origin || event.source !== frame.contentWindow || !event.data) return;
            const current = state(win.location.href, config).sport;
            const currentSport = current.id;
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
        return { render, choose, chooseView, state: () => state(win.location.href, config) };
    }
    return { state, navigate, skateURL, catalogURL, mergeSkateURL, nextIndex, mount };
});
