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

    // ---- Query understanding --------------------------------------------

    const STORE_LABELS = { SkateWarehouse: "Skate Warehouse", SPoT: "Skate Park of Tampa", SoCal: "SoCal Skateshop" };

    function money(value) {
        return "$" + (Number.isInteger(value) ? String(value) : value.toFixed(2));
    }

    function numberText(value) {
        return String(Math.round(value * 1000) / 1000);
    }

    // Each pattern: a regex over the raw query and what a match means. They
    // run in this order and never overlap, so "under 8.5" is a price cap and
    // never also a deck width.
    const PATTERNS = [
        {
            kind: "priceMax",
            re: /(^|[^\w$])((?:under|below|less than|up to|max|<=?)\s*\$?\s*(\d{1,4}(?:\.\d{1,2})?))(?![\d.%])/gi,
            read: match => ({ value: parseFloat(match[3]) })
        },
        {
            kind: "priceMin",
            re: /(^|[^\w$])((?:over|above|more than|min|>=?)\s*\$?\s*(\d{1,4}(?:\.\d{1,2})?))(?![\d.%])/gi,
            read: match => ({ value: parseFloat(match[3]) })
        },
        {
            kind: "discountMin",
            re: /(^|[^\w.])((\d{1,2})\s*%\s*(?:off\b|\+|or more\b)?\+?)/gi,
            read: match => ({ value: parseInt(match[3], 10) })
        },
        {
            // 101a/95a: a double duro, both in one token.
            kind: "duros",
            re: /(^|[^\w.])((\d{2,3})\s*([abd])\s*[\/&,+]\s*(\d{2,3})\s*([abd]))(?![\w])/gi,
            read: match => ({ value: [duroToA(match[3] + match[4]), duroToA(match[5] + match[6])], typed: [match[3] + match[4], match[5] + match[6]] })
        },
        {
            kind: "duros",
            re: /(^|[^\w.])((\d{2,3})\s*([abd]))(?![\w])/gi,
            read: match => ({ value: [duroToA(match[3] + match[4])], typed: [match[3] + match[4]] })
        },
        {
            kind: "diameter",
            re: /(^|[^\w.])((\d{2}(?:\.\d)?)\s*mm)(?![\w])/gi,
            read: match => ({ value: parseFloat(match[3]) })
        },
        {
            // 8.25, 8.25in, 8.25", 8 inch. A whole number needs its unit.
            kind: "width",
            re: /(^|[^\w.$])((\d{1,2}(?:\.\d{1,3})?)\s*("|”|″|inch(?:es)?\b|in\b)?)(?![\w.%])/gi,
            read: match => (match[4] || match[3].indexOf(".") >= 0 ? { value: parseFloat(match[3]) } : null)
        }
    ];

    const VALID = {
        priceMax: value => value > 0,
        priceMin: value => value >= 0,
        discountMin: value => value > 0 && value < 100,
        duros: value => value.every(duro => duro && parseInt(duro, 10) >= 70 && parseInt(duro, 10) <= 110),
        diameter: value => value >= 40 && value <= 75,
        width: value => value >= 7 && value <= 10.5
    };

    // "84b (104a)": what was typed, and the A scale when that differs.
    function duroLabel(typed, value) {
        return typed.map((text, index) => {
            const own = text.toLowerCase();
            return own === value[index] ? own : own + " (" + value[index] + ")";
        }).join("/");
    }

    function label(kind, value) {
        if (kind === "priceMax") return "< " + money(value);
        if (kind === "priceMin") return "> " + money(value);
        if (kind === "discountMin") return value + "%+ off";
        if (kind === "duros") return value.join("/");
        if (kind === "diameter") return numberText(value) + "mm";
        if (kind === "width") return numberText(value) + '"';
        if (kind === "store") return STORE_LABELS[value] || value;
        return value;
    }

    function overlaps(spans, start, end) {
        return spans.some(span => start < span.end && end > span.start);
    }

    // Stores and categories: whole words, through the alias file, longest first.
    function phraseTokens(text, spans, kind, map) {
        const found = [];
        const tokens = [];
        const re = /[A-Za-z0-9][A-Za-z0-9.'-]*/g;
        let match;
        while ((match = re.exec(text))) tokens.push({ start: match.index, end: match.index + match[0].length, word: basic(match[0]) });
        for (let i = 0; i < tokens.length; i++) {
            for (let size = Math.min(4, tokens.length - i); size > 0; size--) {
                const start = tokens[i].start;
                const end = tokens[i + size - 1].end;
                const key = tokens.slice(i, i + size).map(token => token.word).join(" ");
                const value = map.get(key);
                if (!value || overlaps(spans, start, end)) continue;
                found.push({ kind: kind, value: value, start: start, end: end });
                spans.push({ start: start, end: end });
                i += size - 1;
                break;
            }
        }
        return found;
    }

    /**
     * Pull filters out of a typed query.
     *
     * ``{ filters, remainingText, tokens }``: ``filters`` holds diameter (mm),
     * duros (A scale, all required), width (inches), priceMin, priceMax,
     * discountMin, stores and parts (any of them); ``tokens`` lists what was read, with its place in ``text`` (for
     * chips); ``remainingText`` is the rest, for the fuzzy search.
     */
    function parseQuery(text) {
        const raw = String(text == null ? "" : text);
        const spans = [];
        const tokens = [];
        PATTERNS.forEach(pattern => {
            pattern.re.lastIndex = 0;
            let match;
            while ((match = pattern.re.exec(raw))) {
                const start = match.index + match[1].length;
                const end = start + match[2].length;
                const read = pattern.read(match);
                if (!read || !VALID[pattern.kind](read.value) || overlaps(spans, start, end)) continue;
                spans.push({ start: start, end: end });
                tokens.push({ kind: pattern.kind, value: read.value, typed: read.typed, start: start, end: end });
            }
        });
        phraseTokens(raw, spans, "store", vocabulary.stores).forEach(token => tokens.push(token));
        phraseTokens(raw, spans, "part", vocabulary.categories).forEach(token => tokens.push(token));
        tokens.sort((a, b) => a.start - b.start);
        const filters = {};
        tokens.forEach(token => {
            token.raw = raw.slice(token.start, token.end);
            token.label = token.kind === "duros" ? duroLabel(token.typed, token.value) : label(token.kind, token.value);
            // Several stores or categories widen the search: any of them.
            if (token.kind === "duros") filters.duros = (filters.duros || []).concat(token.value);
            else if (token.kind === "store") filters.stores = (filters.stores || []).concat(token.value);
            else if (token.kind === "part") filters.parts = (filters.parts || []).concat(token.value);
            else filters[token.kind] = token.value;
        });
        let rest = "";
        let at = 0;
        spans.slice().sort((a, b) => a.start - b.start).forEach(span => {
            rest += raw.slice(at, span.start) + " ";
            at = span.end;
        });
        rest += raw.slice(at);
        return { filters: filters, tokens: tokens, remainingText: rest.replace(/\s+/g, " ").trim() };
    }

    /** ``text`` without one parsed token (a removed chip). */
    function queryWithout(text, token) {
        const raw = String(text || "");
        return (raw.slice(0, token.start) + " " + raw.slice(token.end)).replace(/\s+/g, " ").trim();
    }

    function nameSizes(name) {
        const sizes = [];
        const re = /(\d{2}(?:\.\d)?)\s*mm\b/gi;
        let match;
        while ((match = re.exec(String(name || "")))) sizes.push(parseFloat(match[1]));
        return sizes;
    }

    function rowDuros(data) {
        const listed = String(data.duros || "").split(",").map(duroToA);
        const named = words(basic(data.name)).filter(word => /^\d{2,3}a$/.test(word));
        return listed.concat(named).filter(Boolean);
    }

    /**
     * Whether a row passes the spec filters a query typed (diameter, duros,
     * width). Store, category, price and discount are applied by the page,
     * merged with the sidebar. ``near`` widens a diameter by that many mm.
     */
    function rowAllows(filters, row, near) {
        const data = (row && row.dataset) || row || {};
        if (!filters) return true;
        if (filters.diameter != null) {
            const reach = (near || 0) + 0.01;
            if (!nameSizes(data.name).some(size => Math.abs(size - filters.diameter) < reach)) return false;
        }
        if (filters.duros && filters.duros.length) {
            const have = rowDuros(data);
            if (!filters.duros.every(duro => have.indexOf(duro) >= 0)) return false;
        }
        if (filters.width != null && !(Math.abs(parseFloat(data.size) - filters.width) < 0.001)) return false;
        return true;
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
        parseQuery: parseQuery,
        queryWithout: queryWithout,
        rowAllows: rowAllows,
        matchesText: matchesText,
        basic: basic,
        duroToA: duroToA,
        normalize: normalize,
        docFromRow: docFromRow,
        createIndex: createIndex,
        search: search
    };
});
