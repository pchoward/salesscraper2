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

    function normalize(text) {
        return String(text == null ? "" : text)
            .toLowerCase()
            .normalize("NFKD")
            .replace(/[̀-ͯ]/g, "")
            .replace(/[^a-z0-9.]+/g, " ")
            .replace(/(^|\s)\.+|\.+(?=\s|$)/g, " ")
            .replace(/\s+/g, " ")
            .trim();
    }

    function words(text) {
        return text ? text.split(" ").filter(Boolean) : [];
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
            store: data.store || "",
            tags: [data.shape, data.duros, data.size].filter(Boolean).join(" ")
        };
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
                fuzzy: term => (term.length >= FUZZY_MIN_TERM ? FUZZY : false),
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

    return {
        normalize: normalize,
        docFromRow: docFromRow,
        createIndex: createIndex,
        search: search
    };
});
