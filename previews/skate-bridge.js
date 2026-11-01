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
