/*
 * SkateDeals search: typo-tolerant matching and ranking over the deal list.
 *
 * DOM-free, so the same file runs in the page (inlined by page.py, after
 * vendor/minisearch.js) and in Node tests (require). page.js hands it the
 * deal rows once; everything after that is in memory.
 */
(function (root, factory) {
    if (typeof module === "object" && module.exports) {
        module.exports = factory(require("./vendor/minisearch.js"));
    } else {
        root.SkateSearch = factory(root.MiniSearch);
    }
})(typeof self !== "undefined" ? self : this, function (MiniSearch) {
    "use strict";

    const FIELDS = ["brand", "name", "category", "store", "tags"];
    // Brand and product name decide a match; store and specs only help.
    const BOOST = { brand: 3, name: 3, category: 1.5, store: 0.5, tags: 0.5 };
    // Queries this short match anywhere in a word, ranked word-start first.
    const SHORT_QUERY = 2;
    const FUZZY = 0.2;
    const FUZZY_MIN_TERM = 3;

    // ---- Normalization -------------------------------------------------

    // Durometer on the A scale: Spitfire's "d" already is; B reads 20 lower.
    function duroToA(token) {
        const match = /^(\d{2,3})([abd])$/.exec(String(token || "").trim().toLowerCase());
        if (!match) return "";
        const value = parseInt(match[1], 10) + (match[2] === "b" ? 20 : 0);
        return value + "a";
    }

    // Lowercase words with skate units unified: "O.J." -> "oj", "54 mm" ->
    // "54mm", 8.25" and "8.25in" -> "8.25", "101a/95a" -> "101a 95a", and
    // every durometer on the A scale ("84b" -> "104a").
    function basic(text) {
        const spaced = String(text == null ? "" : text)
            .toLowerCase()
            .normalize("NFKD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/\b(?:[a-z]\.){2,}/g, match => match.replace(/\./g, "") + " ")
            .replace(/(\d)\s*mm\b/g, "$1mm ")
            .replace(/(\d)\s*(?:"|\u201d|\u2033|''|inch(?:es)?\b|in\b)/g, "$1 ")
            .replace(/[^a-z0-9.]+/g, " ");
        return words(spaced).map(token => {
            const clean = /^\d+\.\d+/.test(token) ? token.replace(/\.+$/, "") : token.replace(/\./g, "");
            return duroToA(clean) || clean;
        }).filter(Boolean).join(" ");
    }

    // Aliases (search/aliases.json): phrase -> canonical, both normalized.
    let vocabulary = { phrases: new Map(), longest: 1, stores: new Map(), categories: new Map(), terms: [] };

    function configure(aliases) {
        const phrases = new Map();
        const stores = new Map();
        const categories = new Map();
        const terms = [];
        let longest = 1;
        function add(map, canonical, alias) {
            const key = basic(alias);
            if (!key) return;
            map.set(key, canonical);
            longest = Math.max(longest, key.split(" ").length);
        }
        ["brands", "models"].forEach(group => {
            Object.keys((aliases && aliases[group]) || {}).forEach(name => {
                const canonical = basic(name);
                terms.push({ group: group, name: name, key: canonical });
                add(phrases, canonical, name);
                (aliases[group][name] || []).forEach(alias => add(phrases, canonical, alias));
            });
        });
        [["stores", stores], ["categories", categories]].forEach(([group, map]) => {
            Object.keys((aliases && aliases[group]) || {}).forEach(name => {
                add(map, name, name);
                (aliases[group][name] || []).forEach(alias => add(map, name, alias));
            });
        });
        vocabulary = { phrases: phrases, longest: longest, stores: stores, categories: categories, terms: terms };
        return vocabulary;
    }

    // Greedy, longest phrase first, so "powell peralta" is one brand and
    // never "powell peralta peralta".
    function applyAliases(tokens) {
        const out = [];
        for (let i = 0; i < tokens.length;) {
            let matched = 0;
            for (let size = Math.min(vocabulary.longest, tokens.length - i); size > 0; size--) {
                const canonical = vocabulary.phrases.get(tokens.slice(i, i + size).join(" "));
                if (canonical) {
                    out.push(canonical);
                    matched = size;
                    break;
                }
            }
            if (matched) i += matched;
            else out.push(tokens[i++]);
        }
        return out;
    }

    function normalize(text) {
        return applyAliases(words(basic(text))).join(" ");
    }

    function words(text) {
        return text ? String(text).split(/\s+/).filter(Boolean) : [];
    }

    // One searchable document per deal row. ``row`` is anything with a
    // ``dataset`` like the page's <tr class="deal-row">.
    function docFromRow(row) {
        const data = (row && row.dataset) || row || {};
        return {
            id: String(data.id || ""),
            name: data.name || "",
            brand: data.brand || "",
            category: data.part || "",
            store: storeWords(data.store || ""),
            tags: [data.shape, String(data.duros || "").replace(/,/g, " "), data.size].filter(Boolean).join(" ")
        };
    }

    // "SkateWarehouse" is also "skate warehouse": every way the store is typed.
    function storeWords(store) {
        const names = [store];
        vocabulary.stores.forEach((canonical, alias) => { if (canonical === store) names.push(alias); });
        return names.join(" ");
    }

    function prepare(doc) {
        const out = { id: doc.id };
        FIELDS.forEach(field => { out[field] = normalize(doc[field]); });
        out.hay = " " + FIELDS.map(field => out[field]).join(" ") + " ";
        return out;
    }

    function createIndex(docs) {
        const mini = new MiniSearch({
            fields: FIELDS,
            tokenize: words,
            processTerm: term => term || null,
            searchOptions: {
                boost: BOOST,
                prefix: true,
                // Sizes and durometers are exact: 104a is not a typo of 101a.
                fuzzy: term => (term.length >= FUZZY_MIN_TERM && !/\d/.test(term) ? FUZZY : false),
                combineWith: "AND"
            }
        });
        const byId = new Map();
        const prepared = (docs || []).map(prepare).filter(doc => doc.id && !byId.has(doc.id) && byId.set(doc.id, doc));
        mini.addAll(prepared);
        return { mini: mini, docs: byId };
    }

    // ``bo``: Bones (word start) before "Combo" (mid-word).
    function shortHits(index, query) {
        const hits = new Map();
        index.docs.forEach(doc => {
            const at = doc.hay.indexOf(query);
            if (at < 0) return;
            const wordStart = doc.hay.indexOf(" " + query) >= 0;
            const field = wordStart && (doc.brand.startsWith(query) || doc.name.startsWith(query)) ? 1 : 0;
            hits.set(doc.id, (wordStart ? 2 : 1) + field);
        });
        return hits;
    }

    /** Map of id -> score for the deals ``query`` matches; null for an empty query. */
    function search(index, query) {
        const text = normalize(query);
        if (!text) return null;
        if (text.length <= SHORT_QUERY && text.indexOf(" ") < 0) return shortHits(index, text);
        const hits = new Map();
        index.mini.search(text).forEach(result => hits.set(String(result.id), result.score));
        return hits;
    }

    // For lists outside the index (Disappeared, All-time lows): every query
    // word starts some word of ``hay``, after normalization and aliases.
    function matchesText(query, hay) {
        const wanted = words(normalize(query));
        if (!wanted.length) return true;
        const have = words(normalize(hay));
        return wanted.every(term => have.some(word => word.startsWith(term)));
    }

    return {
        configure: configure,
        matchesText: matchesText,
        basic: basic,
        duroToA: duroToA,
        normalize: normalize,
        docFromRow: docFromRow,
        createIndex: createIndex,
        search: search
    };
});
