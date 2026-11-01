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
    const NAV_KEYS = ["sport", "discipline"];
    function state(url, config) {
        const parsed = new URL(url);
        const sport = config.sports.find(item => item.id === parsed.searchParams.get("sport")) || config.sports.find(item => item.id === config.defaultSport);
        return { sport };
    }
    function navigate(url, config, sportId) {
        const next = new URL(url);
        const sport = config.sports.find(item => item.id === sportId) || config.sports.find(item => item.id === config.defaultSport);
        next.searchParams.set("sport", sport.id);
        next.searchParams.delete("discipline");
        return next;
    }
    function skateURL(url, config) {
        const parent = new URL(url);
        const skate = config.sports.find(item => item.id === "skate");
        const next = new URL(skate.catalog, parent);
        next.search = parent.search;
        NAV_KEYS.forEach(key => next.searchParams.delete(key));
        next.hash = parent.hash;
        return next;
    }
    function mergeSkateURL(parentURL, childURL, config) {
        const parent = new URL(parentURL);
        const child = new URL(childURL);
        const expected = skateURL(parentURL, config);
        if (child.origin !== parent.origin || child.pathname !== expected.pathname) throw new Error("Unexpected child URL");
        // Remove only production-owned keys. Unknown legacy/analytics parameters
        // survive even when the embedded app's normalizer does not know them.
        (config.skateQueryKeys || []).forEach(key => parent.searchParams.delete(key));
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
        brand.textContent = config.brand.name;
        brand.title = config.brand.domain || "Back to Skate";
        function choose(sportId, focusGroup) {
            const next = navigate(win.location.href, config, sportId);
            if (next.href !== win.location.href) win.history.pushState(win.history.state || {}, "", next);
            render(focusGroup);
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
            if (state(win.location.href, config).sport.id !== "skate" || !frame.dataset.ready) return;
            const expected = skateURL(win.location.href, config);
            if (frame.dataset.currentURL !== expected.href) return;
            frame.contentWindow.postMessage({ type: "shreddeals:restore", href: expected.href, state: historyState && historyState.skateState || null }, win.location.origin);
        }
        function render(focusGroup) {
            const current = state(win.location.href, config);
            tabs(sportTabs, config.sports, current.sport.id, "sport-", "sportPanel", id => choose(id, "sport"));
            doc.getElementById("sportPanel").setAttribute("aria-labelledby", "sport-" + current.sport.id);
            doc.title = config.brand.name + " · " + current.sport.label + " preview";
            const skate = current.sport.id === "skate";
            frame.hidden = !skate;
            frame.setAttribute("aria-hidden", String(!skate));
            frame.tabIndex = skate ? 0 : -1;
            empty.hidden = skate;
            const note = doc.getElementById("contextNote");
            if (skate) {
                note.textContent = "Skate · saved SkateDeals catalog. Development preview; live delivery is disabled.";
                const target = skateURL(win.location.href, config).href;
                if (frame.dataset.currentURL !== target) {
                    delete frame.dataset.ready;
                    frame.dataset.currentURL = target;
                    frame.src = target;
                }
            } else {
                note.textContent = current.sport.label + " · navigation prototype";
                doc.getElementById("emptyTitle").textContent = current.sport.label;
                doc.getElementById("emptyDescription").textContent = "Inventory for " + current.sport.label + " has not been connected.";
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
            const currentSport = state(win.location.href, config).sport.id;
            if (event.data.type === "shreddeals:back") { if (currentSport === "skate") win.history.back(); return; }
            if (event.data.type !== "shreddeals:skate-url") return;
            try {
                const next = mergeSkateURL(win.location.href, event.data.href, config);
                frame.dataset.ready = "true";
                if (currentSport !== "skate") {
                    // A late load while hidden must not rewrite the active sport.
                    frame.dataset.currentURL = skateURL(win.location.href, config).href;
                    return;
                }
                // Cache the shell's logical URL, including retained unknown keys,
                // rather than reloading whenever the embedded normalizer drops one.
                frame.dataset.currentURL = skateURL(next, config).href;
                const method = event.data.action === "push" ? "pushState" : "replaceState";
                win.history[method]({ skateState: event.data.state || null }, "", next);
            } catch (_) { /* Ignore foreign paths and malformed messages. */ }
        });
        brand.addEventListener("click", () => choose("skate", "sport"));
        doc.getElementById("backToSkate").addEventListener("click", () => choose("skate", "sport"));
        render();
        return { render, choose, state: () => state(win.location.href, config) };
    }
    return { state, navigate, skateURL, mergeSkateURL, nextIndex, mount };
});
