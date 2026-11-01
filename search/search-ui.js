/*
 * The search box: suggestions, chips for filters read from the query,
 * highlighted matches, keyboard use, recent searches, and help when nothing
 * matches. Inlined by page.py after page.js, whose state, filters and rows it
 * uses (typedSearch, ensureSearchIndex, applyFilters, rowMatches...).
 */
(function () {
    "use strict";
    if (typeof SkateSearch === "undefined") return;

    const RECENT_KEY = "salesscraper2.recentSearches";
    const RECENT_MAX = 5;
    const SUGGEST_MAX = 8;
    let input = null;
    let list = null;
    let chips = null;
    let options = [];
    let active = -1;

    // ---- Recent searches (this browser only; fine without storage) -------

    function recent() {
        try {
            const saved = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
            return Array.isArray(saved) ? saved.filter(item => typeof item === "string").slice(0, RECENT_MAX) : [];
        } catch (err) {
            return [];
        }
    }

    function remember(query) {
        const text = String(query || "").trim();
        if (text.length < 2) return;
        try {
            const next = [text].concat(recent().filter(item => item.toLowerCase() !== text.toLowerCase())).slice(0, RECENT_MAX);
            localStorage.setItem(RECENT_KEY, JSON.stringify(next));
        } catch (err) {
            /* private mode: no recent searches */
        }
    }

    // ---- Highlighting --------------------------------------------------

    // ``text`` into ``node`` with the query's matches in <mark>. Text nodes
    // only, never HTML from data.
    function writeHighlighted(node, text, query) {
        const ranges = query ? SkateSearch.highlightRanges(text, query) : [];
        node.replaceChildren();
        let at = 0;
        ranges.forEach(([start, end]) => {
            if (start > at) node.appendChild(document.createTextNode(text.slice(at, start)));
            const mark = document.createElement("mark");
            mark.className = "search-hit";
            mark.textContent = text.slice(start, end);
            node.appendChild(mark);
            at = end;
        });
        if (at < text.length) node.appendChild(document.createTextNode(text.slice(at)));
    }

    function paintTitle(node) {
        if (node.dataset.plain == null) node.dataset.plain = node.textContent;
        const query = input ? input.value.trim() : "";
        if (node.dataset.marked === query) return;
        node.dataset.marked = query;
        writeHighlighted(node, node.dataset.plain, query);
    }

    function highlightCards(root) {
        (root || document).querySelectorAll("#cardGrid .deal-card .product-name").forEach(paintTitle);
    }

    // ---- Suggestions ---------------------------------------------------

    function close() {
        if (!list) return;
        list.hidden = true;
        list.replaceChildren();
        options = [];
        active = -1;
        input.setAttribute("aria-expanded", "false");
        input.removeAttribute("aria-activedescendant");
    }

    function setActive(index) {
        const nodes = list.querySelectorAll(".search-option");
        if (!nodes.length) return;
        active = (index + nodes.length) % nodes.length;
        nodes.forEach((node, i) => node.setAttribute("aria-selected", i === active ? "true" : "false"));
        input.setAttribute("aria-activedescendant", nodes[active].id);
        nodes[active].scrollIntoView({ block: "nearest" });
    }

    function render() {
        if (!input || !list) return;
        const text = input.value;
        let entries;
        if (!text.trim()) {
            entries = recent().map(query => ({ group: "Recent searches", kind: "recent", label: query, value: query }));
        } else {
            entries = SkateSearch.suggest(ensureSearchIndex(), text, SUGGEST_MAX);
        }
        if (!entries.length || document.activeElement !== input) {
            close();
            return;
        }
        options = entries;
        active = -1;
        list.replaceChildren();
        let group = null;
        let groupNode = null;
        entries.forEach((entry, index) => {
            if (entry.group !== group) {
                group = entry.group;
                groupNode = document.createElement("div");
                groupNode.setAttribute("role", "group");
                const head = document.createElement("div");
                head.className = "search-suggest-head";
                head.id = "searchGroup" + index;
                head.setAttribute("role", "presentation");
                head.textContent = group;
                groupNode.setAttribute("aria-labelledby", head.id);
                groupNode.appendChild(head);
                list.appendChild(groupNode);
            }
            const option = document.createElement("div");
            option.className = "search-option search-option-" + entry.kind;
            option.id = "searchOption" + index;
            option.setAttribute("role", "option");
            option.setAttribute("aria-selected", "false");
            const label = document.createElement("span");
            label.className = "search-option-label";
            writeHighlighted(label, entry.label, entry.kind === "recent" ? "" : text);
            option.appendChild(label);
            if (entry.count) {
                const count = document.createElement("span");
                count.className = "search-option-count";
                count.textContent = String(entry.count);
                count.setAttribute("aria-label", entry.count + (entry.count === 1 ? " deal" : " deals"));
                option.appendChild(count);
            }
            // mousedown, so the input keeps focus and blur does not close first.
            option.addEventListener("mousedown", event => {
                event.preventDefault();
                choose(index);
            });
            groupNode.appendChild(option);
        });
        list.hidden = false;
        input.setAttribute("aria-expanded", "true");
    }

    // The query without its free text: what the parser read stays.
    function filtersOnly(text) {
        return SkateSearch.parseQuery(text).tokens.map(token => token.raw).join(" ");
    }

    function run(text) {
        input.value = text;
        clearTimeout(filterTimer);
        syncSearchSort();
        applyFilters();
    }

    function choose(index) {
        const entry = options[index];
        if (!entry) return;
        const text = input.value;
        if (entry.kind === "brand") {
            // A brand applies the sidebar's brand filter; its typed words go.
            // A brand with nothing in this category opens the one it has
            // (or all of them), instead of an empty page.
            setSelect("brandSelect", entry.value);
            const parts = {};
            dealRows().forEach(row => {
                if (brandSame(row.dataset.brand, entry.value)) parts[row.dataset.part || ""] = true;
            });
            const current = state.part || "all";
            const found = Object.keys(parts).filter(Boolean);
            if (current !== "all" && !parts[current] && found.length) filterByPart(found.length === 1 ? found[0] : "all");
            run(filtersOnly(text));
        } else if (entry.kind === "size") {
            run(text.replace(/(\d{1,3}(?:\.\d{0,3})?)\s*$/, "") + entry.value);
        } else if (entry.kind === "model") {
            const words = text.trim().split(/\s+/);
            words.pop();
            run((words.join(" ") + " " + entry.value).trim());
        } else {
            run(entry.value);
        }
        remember(input.value);
        close();
        input.focus();
    }

    function onKeydown(event) {
        const open = !list.hidden;
        if (event.key === "ArrowDown") {
            event.preventDefault();
            if (!open) render();
            setActive(active + 1);
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            if (!open) render();
            setActive(active < 0 ? -1 : active - 1);
        } else if (event.key === "Enter") {
            if (open && active >= 0) {
                event.preventDefault();
                choose(active);
                return;
            }
            close();
            remember(input.value);
            clearTimeout(filterTimer);
            applyFilters();
        } else if (event.key === "Escape") {
            if (open) {
                event.preventDefault();
                event.stopPropagation();
                close();
            }
        }
    }

    // "/" searches from anywhere, unless typing somewhere else.
    function onDocumentKeydown(event) {
        if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
        const target = event.target;
        const tag = target && target.tagName ? target.tagName.toLowerCase() : "";
        if (tag === "input" || tag === "textarea" || tag === "select" || (target && target.isContentEditable)) return;
        event.preventDefault();
        input.focus();
        input.select();
    }

    // ---- Chips ---------------------------------------------------------

    function paintChips() {
        if (!chips) return;
        const text = input.value;
        const parsed = SkateSearch.parseQuery(text);
        chips.replaceChildren();
        parsed.tokens.forEach(token => {
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "search-chip";
            chip.setAttribute("aria-label", "Remove " + token.label + " from the search");
            chip.textContent = token.label + " ";
            const x = document.createElement("span");
            x.setAttribute("aria-hidden", "true");
            x.textContent = "×";
            chip.appendChild(x);
            chip.addEventListener("click", () => {
                run(SkateSearch.queryWithout(input.value, token));
                input.focus();
            });
            chips.appendChild(chip);
        });
        const typed = typedSearch(state.search);
        if (typed && typed.filters.partsInferred) {
            const note = document.createElement("span");
            note.className = "search-chip is-inferred";
            note.textContent = "Showing " + typed.filters.parts.join(", ");
            note.title = "Nothing in " + state.part + " matches this search, so it covers the categories that do.";
            chips.appendChild(note);
        }
        chips.hidden = !chips.children.length;
    }

    // ---- Nothing matches: a suggestion, then close matches ---------------

    function rowsMatching(over) {
        return dealRows().filter(row => rowMatches(row, over));
    }

    function dealLink(row) {
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = row.dataset.url || "#";
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = row.dataset.name || "Deal";
        item.appendChild(link);
        const price = parseFloat(row.dataset.price);
        const meta = document.createElement("span");
        meta.className = "search-rescue-meta";
        meta.textContent = " · " + (row.dataset.store || "") + (Number.isFinite(price) ? " · $" + price.toFixed(2) : "");
        item.appendChild(meta);
        return item;
    }

    // The first relaxation that finds something: a wheel size within 2mm,
    // then each typed filter left out in turn (price cap first).
    function closeMatches() {
        const query = state.search;
        const parsed = SkateSearch.parseQuery(query);
        if (parsed.filters.diameter != null) {
            const rows = rowsMatching({ searchNear: 2 });
            if (rows.length) return { label: "Close matches: within 2mm of " + parsed.filters.diameter + "mm", rows: rows };
        }
        const order = ["priceMax", "priceMin", "discountMin", "duros", "width", "diameter", "store", "part"];
        for (let i = 0; i < order.length; i++) {
            const token = parsed.tokens.find(entry => entry.kind === order[i]);
            if (!token) continue;
            const rows = rowsMatching({ search: SkateSearch.queryWithout(query, token) });
            if (rows.length) return { label: "Close matches without " + token.label, rows: rows, drop: token };
        }
        return null;
    }

    function paintRescue() {
        const empty = document.getElementById("emptyState");
        const old = document.getElementById("searchRescue");
        if (old) old.remove();
        if (!empty || empty.hidden || !input.value.trim()) return;
        const block = document.createElement("div");
        block.id = "searchRescue";
        block.className = "search-rescue";
        const parsed = SkateSearch.parseQuery(input.value);
        const guess = parsed.remainingText ? SkateSearch.didYouMean(ensureSearchIndex(), parsed.remainingText) : null;
        if (guess) {
            const line = document.createElement("p");
            line.append("Did you mean ");
            const button = document.createElement("button");
            button.type = "button";
            button.className = "text-btn search-rescue-fix";
            button.textContent = guess.label;
            button.addEventListener("click", () => {
                const pattern = new RegExp("\\b" + guess.word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "i");
                run(input.value.replace(pattern, guess.label));
            });
            line.append(button, "?");
            block.appendChild(line);
        }
        const nearby = closeMatches();
        if (nearby) {
            const head = document.createElement("p");
            head.className = "search-rescue-head";
            head.textContent = nearby.label + " (" + nearby.rows.length + ")";
            block.appendChild(head);
            const items = document.createElement("ul");
            items.className = "search-rescue-list";
            nearby.rows.slice(0, 5).forEach(row => items.appendChild(dealLink(row)));
            block.appendChild(items);
            if (nearby.drop) {
                const drop = nearby.drop;
                const button = document.createElement("button");
                button.type = "button";
                button.className = "text-btn";
                button.textContent = "Show all " + nearby.rows.length + " without " + drop.label;
                button.addEventListener("click", () => {
                    const token = SkateSearch.parseQuery(input.value).tokens.find(entry => entry.kind === drop.kind);
                    if (token) run(SkateSearch.queryWithout(input.value, token));
                });
                block.appendChild(button);
            }
        }
        if (!block.children.length) return;
        const heading = empty.querySelector("h3");
        if (heading) heading.after(block);
        else empty.prepend(block);
    }

    // page.js calls this after every filter pass.
    window.afterSearchFilters = function () {
        if (!input) return;
        paintChips();
        highlightCards();
        paintRescue();
    };

    function init() {
        input = document.getElementById("searchInput");
        list = document.getElementById("searchSuggest");
        chips = document.getElementById("searchChips");
        if (!input || !list) return;
        input.addEventListener("input", render);
        input.addEventListener("focus", render);
        input.addEventListener("keydown", onKeydown);
        input.addEventListener("blur", () => {
            setTimeout(close, 120);
            if (visibleDealCount() > 0) remember(input.value);
        });
        document.addEventListener("keydown", onDocumentKeydown);
        const grid = document.getElementById("cardGrid");
        if (grid && typeof MutationObserver === "function") {
            new MutationObserver(records => {
                if (!input.value.trim() && !grid.querySelector("mark.search-hit")) return;
                records.forEach(record => record.addedNodes.forEach(node => {
                    if (node.nodeType === 1 && node.classList.contains("deal-card")) {
                        const title = node.querySelector(".product-name");
                        if (title) paintTitle(title);
                    }
                }));
            }).observe(grid, { childList: true });
        }
        window.afterSearchFilters();
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
