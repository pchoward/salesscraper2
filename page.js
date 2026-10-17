let state = {
    store: "all",
    part: "Decks",
    widths: [],
    brand: "all",
    length: "all",
    wheelbase: "all",
    watching: false,
    cardNew: false,
    cardDrop: false,
    cardLow: false,
    // Digest chip. "all" is the default and is not a table filter.
    // visitMode only chooses which baseline those counts use.
    change: "all",
    grouped: false,
    dropInterval: "all",
    kinds: [],
    highlights: false,
    diameters: [],
    duros: [],
    shapes: [],
    truckSizes: [],
    truckHeights: [],
    constructions: [],
    abecs: [],
    shoeSizes: [],
    visitMode: "yesterday",
    sortKey: "rank",
    sortDir: "asc",
    search: ""
};

const STAR_KEY = "salesscraper2.stars";
const SNAP_KEY = "salesscraper2.snapshot";
const VIEWS_KEY = "salesscraper2.views";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
let visitGone = [];
let sparkTip = null;
let sparkPinned = false;
let renamingId = "";

let catalogData = null;
let rowList = null;
let rowById = null;
let cardById = null;
let detailById = null;
let matchMemo = null;
let scanDayValue = null;

function catalog() {
    if (catalogData) return catalogData;
    const node = document.getElementById("catalogJson");
    if (!node) return { items: {}, views: [] };
    try {
        catalogData = JSON.parse(node.textContent);
    } catch (err) {
        catalogData = { items: {}, views: [] };
    }
    return catalogData;
}

function scanDay() {
    if (scanDayValue == null) scanDayValue = String((catalog().generated || "")).slice(0, 10);
    return scanDayValue;
}

function indexDeals() {
    if (rowList) return;
    rowList = Array.from(document.querySelectorAll("#mainTable .deal-row"));
    rowById = new Map();
    rowList.forEach(row => rowById.set(row.dataset.id, row));
    cardById = new Map();
    document.querySelectorAll("#cardGrid .deal-card").forEach(card => {
        cardById.set(card.dataset.id, card);
    });
    detailById = new Map();
    document.querySelectorAll("#mainTable .detail-row").forEach(detail => {
        detailById.set(detail.dataset.for, detail);
    });
}

function dealRows() {
    indexDeals();
    return rowList;
}

function cardFor(id) {
    indexDeals();
    return cardById.get(id) || null;
}

function readJson(key, fallback) {
    try {
        const raw = localStorage.getItem(key);
        if (!raw) return fallback;
        return JSON.parse(raw);
    } catch (err) {
        return fallback;
    }
}

function writeJson(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (err) {
        /* private mode and full storage should not break the page */
    }
}

function starSet() {
    const stored = readJson(STAR_KEY, []);
    return new Set(Array.isArray(stored) ? stored : []);
}

function numOrNull(id) {
    const node = document.getElementById(id);
    if (!node || node.value === "") return null;
    const value = parseFloat(node.value);
    return Number.isFinite(value) ? value : null;
}

function numText(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "";
    if (Math.abs(number - Math.round(number)) < 1e-9) return String(Math.round(number));
    return number.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
}

function widthRanges() {
    return (typeof WIDTH_RANGES === "undefined") ? [] : WIDTH_RANGES;
}

function readControls() {
    const search = document.getElementById("searchInput");
    state.search = search ? search.value.toLowerCase().trim() : "";
    state.priceMin = numOrNull("priceMin");
    state.priceMax = numOrNull("priceMax");
    state.discountMin = numOrNull("discountMin");
    state.discountMax = numOrNull("discountMax");
    state.scoreMin = numOrNull("scoreMin");
    state.scoreMax = numOrNull("scoreMax");
    const brand = document.getElementById("brandSelect");
    const length = document.getElementById("lengthSelect");
    const wheelbase = document.getElementById("wheelbaseSelect");
    if (brand) state.brand = brand.value || "all";
    if (length) state.length = length.value || "all";
    if (wheelbase) state.wheelbase = wheelbase.value || "all";
}

// Keep in sync with query_state.bucket_contains / parse_width_param.
// Width ranges filter deck rows only. Wheels, trucks, and bearings stay
// visible when a range is selected; they disappear only when Type is Decks.
// A deck with no parsed width matches no bucket, so it hides while any
// range is selected.
function bucketContains(range, width) {
    if (!range || !Number.isFinite(width)) return false;
    const lo = range.min == null ? null : Number(range.min);
    const hi = range.max == null ? null : Number(range.max);
    if (lo != null && width < lo - 1e-9) return false;
    if (hi != null && width >= hi - 1e-9) return false;
    return true;
}

function bucketForWidth(width) {
    const ranges = widthRanges();
    for (let i = 0; i < ranges.length; i++) {
        if (bucketContains(ranges[i], width)) return ranges[i].id;
    }
    return "";
}

function bucketsOverlapping(low, high) {
    const left = low == null ? -Infinity : low;
    const right = high == null ? Infinity : high;
    const ids = [];
    widthRanges().forEach(range => {
        const lo = range.min == null ? -Infinity : Number(range.min);
        const hi = range.max == null ? Infinity : Number(range.max);
        if (left < hi - 1e-12 && right >= lo - 1e-12) ids.push(range.id);
    });
    return ids;
}

function orderedWidths(ids) {
    const chosen = {};
    (ids || []).forEach(id => { chosen[id] = true; });
    return widthRanges().map(range => range.id).filter(id => chosen[id]);
}

function parseWidthParam(value) {
    const text = String(value || "").trim();
    if (!text || text.toLowerCase() === "all") return [];
    const known = {};
    widthRanges().forEach(range => { known[range.id] = true; });
    const aliases = { "<7": "lt7", "<7.0": "lt7", "10+": "10up", "10.0+": "10up" };
    const chosen = [];
    text.split(",").forEach(raw => {
        const token = String(raw || "").replace(/\s+/g, "");
        if (!token) return;
        if (aliases[token]) {
            chosen.push(aliases[token]);
            return;
        }
        if (known[token]) {
            chosen.push(token);
            return;
        }
        const dash = token.indexOf("-");
        if (dash >= 0) {
            const left = token.slice(0, dash);
            const right = token.slice(dash + 1);
            const low = left === "" ? null : Number(left);
            const high = right === "" ? null : Number(right);
            if ((left && !Number.isFinite(low)) || (right && !Number.isFinite(high))) return;
            if (low == null && high == null) return;
            bucketsOverlapping(low, high).forEach(id => chosen.push(id));
            return;
        }
        const number = Number(token);
        if (Number.isFinite(number)) {
            const id = bucketForWidth(number);
            if (id) chosen.push(id);
        }
    });
    return orderedWidths(chosen);
}

function deckWidthAllowed(row, widths) {
    const selected = widths != null ? widths : (state.widths || []);
    if (!selected.length) return true;
    if ((row.dataset.part || "") !== "Decks") return true;
    const size = parseFloat(row.dataset.size);
    if (!Number.isFinite(size)) return false;
    const ranges = widthRanges();
    return selected.some(id => {
        const range = ranges.find(item => item.id === id);
        return bucketContains(range, size);
    });
}

function widthGroupIds(node) {
    return String((node && node.getAttribute("data-buckets")) || "").split(",").filter(Boolean);
}

function paintWidthChips() {
    const selected = {};
    (state.widths || []).forEach(id => { selected[id] = true; });
    document.querySelectorAll("#sizeFilters .width-chip").forEach(node => {
        const ids = widthGroupIds(node);
        const on = ids.length > 0 && ids.every(id => selected[id]);
        node.classList.toggle("active", on);
        node.classList.toggle("is-partial", !on && ids.some(id => selected[id]));
        node.setAttribute("aria-pressed", on ? "true" : "false");
    });
}

function toggleWidthGroup(node) {
    const ids = widthGroupIds(node);
    if (!ids.length) return;
    if ((state.part || "Decks") === "all") {
        state.part = "Decks";
        const select = document.getElementById("partSelect");
        if (select) select.value = "Decks";
        setPressed("#partFilters [data-part]", "data-part", "Decks");
        syncTypeSections(true);
    }
    const selected = {};
    (state.widths || []).forEach(id => { selected[id] = true; });
    const allOn = ids.every(id => selected[id]);
    ids.forEach(id => {
        if (allOn) delete selected[id];
        else selected[id] = true;
    });
    state.widths = orderedWidths(Object.keys(selected));
    paintWidthChips();
    applyFilters();
}

// Keep in sync with part_specs.DIAMETER_ORDER / SHAPES / HEIGHTS.
const DIAMETER_ORDER = ["50-51", "52-53", "54-55", "56+"];
const SHAPE_ORDER = ["conical", "radial", "sidecut"];
const HEIGHT_ORDER = ["low", "mid", "high"];
const CONSTRUCTION_ORDER = ["hollow", "standard"];
const SPEC_FACETS = [
    { stateKey: "diameters", part: "Wheels", attr: "diameter", section: "diameterFilters" },
    { stateKey: "duros", part: "Wheels", attr: "duros", section: "duroFilters" },
    { stateKey: "shapes", part: "Wheels", attr: "shape", section: "shapeFilters" },
    { stateKey: "truckSizes", part: "Trucks", attr: "trucksize", section: "trucksizeFilters" },
    { stateKey: "truckHeights", part: "Trucks", attr: "truckheight", section: "truckheightFilters" },
    { stateKey: "constructions", part: "Trucks", attr: "construction", section: "constructionFilters" },
    { stateKey: "abecs", part: "Bearings", attr: "abec", section: "abecFilters" },
    { stateKey: "shoeSizes", part: "Sneakers", attr: "shoesize", section: "shoesizeFilters" }
];
const SPEC_OPEN = { width: 1, diameter: 1, duro: 1, shape: 1, trucksize: 1, truckheight: 1, construction: 1, abec: 1, shoesize: 1 };

function normalizeDuroToken(value) {
    const match = String(value || "").trim().toLowerCase().match(/^(\d{2,3})([abd])$/);
    if (!match) return "";
    return String(parseInt(match[1], 10)) + match[2];
}

function normalizeSizeToken(value) {
    const text = String(value || "").trim();
    if (!/^(?:\d{2,3}|\d{1,2}\.\d+)$/.test(text)) return "";
    if (text.indexOf(".") < 0) {
        const token = String(parseInt(text, 10));
        const mm = { "109": 1, "129": 1, "136": 1, "139": 1, "144": 1, "145": 1, "147": 1, "148": 1, "149": 1, "151": 1, "159": 1, "169": 1, "215": 1 };
        const ace = { "22": 1, "33": 1, "44": 1, "55": 1, "60": 1, "66": 1, "77": 1 };
        return (mm[token] || ace[token]) ? token : "";
    }
    const number = parseFloat(text);
    if (!Number.isFinite(number)) return "";
    const token = Math.abs(number - Math.round(number)) < 1e-9
        ? number.toFixed(1)
        : number.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
    const axle = { "5.0": 1, "5.2": 1, "5.6": 1, "5.8": 1, "6.1": 1 };
    if (axle[token] || (number >= 7 && number <= 12)) return token;
    return "";
}

function orderSpecValues(stateKey, values) {
    const chosen = {};
    (values || []).forEach(value => {
        let token = String(value || "").trim();
        if (stateKey === "duros") token = normalizeDuroToken(token);
        else if (stateKey === "truckSizes") token = normalizeSizeToken(token);
        else if (stateKey === "abecs") {
            if (!/^\d{1,2}$/.test(token)) token = "";
            else token = String(parseInt(token, 10));
        } else if (stateKey === "shoeSizes") {
            const number = parseFloat(token);
            if (!Number.isFinite(number) || number < 4 || number > 15) token = "";
            else if (Math.abs(number * 2 - Math.round(number * 2)) > 1e-6) token = "";
            else if (Math.abs(number - Math.round(number)) < 1e-6) token = String(Math.round(number));
            else token = number.toFixed(1);
        } else token = token.toLowerCase();
        if (token) chosen[token] = true;
    });
    const keys = Object.keys(chosen);
    if (stateKey === "diameters") return DIAMETER_ORDER.filter(id => chosen[id]);
    if (stateKey === "shapes") return SHAPE_ORDER.filter(id => chosen[id]);
    if (stateKey === "truckHeights") return HEIGHT_ORDER.filter(id => chosen[id]);
    if (stateKey === "constructions") return CONSTRUCTION_ORDER.filter(id => chosen[id]);
    if (stateKey === "duros") {
        return keys.sort((a, b) => {
            const delta = parseInt(a, 10) - parseInt(b, 10);
            if (delta) return delta;
            return a.slice(-1) < b.slice(-1) ? -1 : a.slice(-1) > b.slice(-1) ? 1 : 0;
        });
    }
    if (stateKey === "truckSizes") return keys.sort((a, b) => parseFloat(a) - parseFloat(b));
    if (stateKey === "abecs") return keys.sort((a, b) => parseInt(a, 10) - parseInt(b, 10));
    if (stateKey === "shoeSizes") return keys.sort((a, b) => parseFloat(a) - parseFloat(b));
    return keys;
}

function activeSpecKeys(part) {
    const current = part || "Decks";
    if (current === "Decks") return ["widths", "length", "wheelbase"];
    if (current === "Wheels") return ["diameters", "duros", "shapes"];
    if (current === "Trucks") return ["truckSizes", "truckHeights", "constructions"];
    if (current === "Bearings") return ["abecs"];
    if (current === "Sneakers") return ["shoeSizes"];
    return [];
}

function specKeyActive(key, part) {
    const current = part != null ? part : (state.part || "Decks");
    return activeSpecKeys(current).indexOf(key) >= 0;
}

function specTokens(row, attr) {
    return String((row.dataset && row.dataset[attr]) || "").split(",").map(token => token.trim()).filter(Boolean);
}

// A wheel, truck, or bearing spec filters only that part. Other parts stay
// visible, the same way a deck width does. A row of that part with no parsed
// value is hidden while the spec is selected.
function specAllowed(row, facet, selected) {
    const chosen = selected || [];
    if (!chosen.length) return true;
    if ((row.dataset.part || "") !== facet.part) return true;
    const tokens = specTokens(row, facet.attr);
    if (!tokens.length) return false;
    return chosen.some(value => tokens.indexOf(value) >= 0);
}

function syncTypeSections(expandSpec) {
    const part = state.part || "Decks";
    const context = document.getElementById("contextSpecs");
    const specs = document.getElementById("productSpecs");
    const specsBody = document.getElementById("productSpecsBody");
    const brand = document.querySelector('[data-section="brand"]');
    const specGroup = document.getElementById("specGroup");
    if (part === "all") {
        if (specs && specsBody && context) specsBody.appendChild(context);
        if (specs) specs.hidden = false;
    } else {
        if (context && specGroup) specGroup.insertBefore(context, specGroup.firstChild);
        else if (context && brand && brand.parentElement) brand.parentElement.insertBefore(context, brand);
        if (specs) specs.hidden = true;
    }
    document.querySelectorAll("#contextSpecs .filter-section[data-for]").forEach(section => {
        const owner = section.getAttribute("data-for") || "";
        const show = part === "all" || owner === part;
        section.classList.toggle("is-type-hidden", !show);
        const id = section.getAttribute("data-section") || "";
        if (show && part !== "all" && expandSpec && SPEC_OPEN[id]) paintFilterSection(section, true);
    });
    rememberFilterSections();
}

function adoptSpecPart(stateKey) {
    const facet = SPEC_FACETS.find(item => item.stateKey === stateKey);
    if (!facet || (state.part || "Decks") !== "all") return;
    state.part = facet.part;
    const select = document.getElementById("partSelect");
    if (select) select.value = state.part;
    setPressed("#partFilters [data-part]", "data-part", state.part);
    syncTypeSections(true);
}

function toggleSpec(stateKey, value) {
    if (!value) return;
    adoptSpecPart(stateKey);
    const selected = {};
    (state[stateKey] || []).forEach(item => { selected[item] = true; });
    if (selected[value]) delete selected[value];
    else selected[value] = true;
    state[stateKey] = orderSpecValues(stateKey, Object.keys(selected));
    applyFilters();
}

function filterBrandList(query) {
    const facet = document.getElementById("brandFacet");
    const text = String(query || "").trim().toLowerCase();
    if (facet) facet.classList.toggle("is-searching", text.length > 0);
    document.querySelectorAll("#brandList .facet-value").forEach(node => {
        const brand = (node.getAttribute("data-brand") || "").toLowerCase();
        const label = (node.textContent || "").toLowerCase();
        const match = !text || (brand !== "all" && (brand.includes(text) || label.includes(text)));
        node.classList.toggle("is-search-hide", !match);
    });
}

function paintBrandFacet() {
    const current = state.brand || "all";
    document.querySelectorAll("#brandList .facet-value").forEach(node => {
        const on = brandSame(node.getAttribute("data-brand") || "", current);
        node.classList.toggle("active", on);
        node.setAttribute("aria-pressed", on ? "true" : "false");
    });
}

function paintSelectCounts(id, counts) {
    const select = document.getElementById(id);
    if (!select) return;
    Array.from(select.options).forEach(option => {
        if (!option.value || option.value === "all") return;
        const count = counts[option.value] || 0;
        const label = option.getAttribute("data-label") || option.textContent.replace(/\s*\(\d+\)\s*$/, "");
        option.textContent = label + " (" + count + ")";
        option.disabled = count === 0 && option.value !== select.value;
    });
}

function paintFacetCounts() {
    const brandCounts = Object.create(null);
    const storeCounts = Object.create(null);
    const partCounts = Object.create(null);
    const lengthCounts = Object.create(null);
    const wheelCounts = Object.create(null);
    const widthCounts = Object.create(null);
    widthRanges().forEach(range => { widthCounts[range.id] = 0; });
    dealRows().forEach(row => {
        if (rowMatches(row, { brand: "all" })) {
            const brand = row.dataset.brand || "";
            if (brand) brandCounts[brand] = (brandCounts[brand] || 0) + 1;
        }
        if (rowMatches(row, { store: "all" })) {
            const store = row.dataset.store || "";
            if (store) storeCounts[store] = (storeCounts[store] || 0) + 1;
        }
        if (rowMatches(row, { part: "all" })) {
            const part = row.dataset.part || "";
            if (part) partCounts[part] = (partCounts[part] || 0) + 1;
        }
        if (rowMatches(row, { length: "all" })) {
            const length = row.dataset.length || "";
            if (length) lengthCounts[length] = (lengthCounts[length] || 0) + 1;
        }
        if (rowMatches(row, { wheelbase: "all" })) {
            const wheel = row.dataset.wheelbase || "";
            if (wheel) wheelCounts[wheel] = (wheelCounts[wheel] || 0) + 1;
        }
        if ((row.dataset.part || "") === "Decks" && rowMatches(row, { widths: [] })) {
            const id = bucketForWidth(parseFloat(row.dataset.size));
            if (id && Object.prototype.hasOwnProperty.call(widthCounts, id)) widthCounts[id] += 1;
        }
    });
    document.querySelectorAll("#brandList .facet-value").forEach(node => {
        const brand = node.getAttribute("data-brand") || "";
        if (!brand || brand === "all") return;
        const count = brandCounts[brand] || 0;
        const slot = node.querySelector(".facet-count");
        if (slot) slot.textContent = "(" + count + ")";
        node.classList.toggle("is-zero", count === 0);
        node.setAttribute("data-count", String(count));
    });
    document.querySelectorAll("#sizeFilters .width-chip").forEach(node => {
        let count = 0;
        widthGroupIds(node).forEach(id => { count += widthCounts[id] || 0; });
        const slot = node.querySelector(".width-count");
        if (slot) slot.textContent = String(count);
        node.classList.toggle("is-zero", count === 0);
        node.setAttribute("data-count", String(count));
    });
    paintSelectCounts("storeSelect", storeCounts);
    paintSelectCounts("partSelect", partCounts);
    paintQuickRow("storeFilters", "data-store", storeCounts, state.store || "all");
    paintQuickRow("partFilters", "data-part", partCounts, state.part || "Decks");
    paintTypeHint();
    paintSelectCounts("lengthSelect", lengthCounts);
    paintSelectCounts("wheelbaseSelect", wheelCounts);
    scheduleNavFit();
    SPEC_FACETS.forEach(facet => {
        const counts = Object.create(null);
        document.querySelectorAll("#" + facet.section + " .spec-chip").forEach(node => {
            counts[node.getAttribute("data-value") || ""] = 0;
        });
        const override = {};
        override[facet.stateKey] = [];
        dealRows().forEach(row => {
            if ((row.dataset.part || "") !== facet.part) return;
            if (!rowMatches(row, override)) return;
            specTokens(row, facet.attr).forEach(token => {
                if (Object.prototype.hasOwnProperty.call(counts, token)) counts[token] += 1;
            });
        });
        document.querySelectorAll("#" + facet.section + " .spec-chip").forEach(node => {
            const value = node.getAttribute("data-value") || "";
            const count = counts[value] || 0;
            const slot = node.querySelector(".spec-count");
            if (slot) slot.textContent = String(count);
            node.classList.toggle("is-zero", count === 0);
            node.setAttribute("data-count", String(count));
            const on = (state[facet.stateKey] || []).indexOf(value) >= 0;
            node.classList.toggle("active", on);
            node.setAttribute("aria-pressed", on ? "true" : "false");
        });
    });
    paintKeepaCounts();
}

function setPressed(selector, attr, value) {
    document.querySelectorAll(selector).forEach(node => {
        const current = node.getAttribute(attr) || "";
        const on = current === value || (value === "all" && current === "all");
        node.classList.toggle("active", on);
        if (node.hasAttribute("aria-pressed")) node.setAttribute("aria-pressed", on ? "true" : "false");
    });
}

function paintCards() {
    document.querySelectorAll("[data-card]").forEach(card => {
        const kind = card.getAttribute("data-card");
        let on = false;
        if (kind === "new") on = state.cardNew;
        if (kind === "drop") on = state.cardDrop;
        if (kind === "lowest") on = state.cardLow;
        if (kind === "store") on = state.store !== "all" && card.getAttribute("data-store") === state.store;
        card.setAttribute("aria-pressed", on ? "true" : "false");
    });
    document.querySelectorAll("[data-change]").forEach(button => {
        const on = button.getAttribute("data-change") === state.change;
        button.setAttribute("aria-pressed", on ? "true" : "false");
        button.classList.toggle("active", on);
    });
}

const DEAL_KINDS = ["new", "drop", "low", "back", "hot"];
const DROP_INTERVALS = { day: 1, week: 7, month: 30, quarter: 90 };

function kindMatch(row, kinds) {
    const selected = kinds || [];
    if (!selected.length) return true;
    return selected.some(kind => {
        if (kind === "new") return row.dataset.fresh === "1";
        if (kind === "drop") return row.dataset.drop === "1";
        if (kind === "low") return row.dataset.lowest === "1";
        if (kind === "back") return row.dataset.back === "1";
        if (kind === "hot") return row.dataset.hot === "1";
        return false;
    });
}

function dropInInterval(row, key) {
    if (!key || key === "all") return true;
    const limit = DROP_INTERVALS[key];
    if (!limit) return true;
    const day = row.dataset.dropday || "";
    if (!day) return false;
    const end = scanDay();
    if (!end) return false;
    return day >= addDays(end, -limit) && day <= end;
}

function rowMatches(row, overrides) {
    const memoKey = matchMemo
        ? (row.dataset.id || "") + "\u0000" + (overrides ? JSON.stringify(overrides) : "")
        : "";
    if (matchMemo && matchMemo.has(memoKey)) return matchMemo.get(memoKey);
    const value = rowMatchesNow(row, overrides);
    if (matchMemo) matchMemo.set(memoKey, value);
    return value;
}

function rowMatchesNow(row, overrides) {
    const over = overrides || {};
    const store = over.store != null ? over.store : state.store;
    const part = over.part != null ? over.part : state.part;
    const brand = over.brand != null ? over.brand : state.brand;
    const length = over.length != null ? over.length : state.length;
    const wheelbase = over.wheelbase != null ? over.wheelbase : state.wheelbase;
    const widths = Object.prototype.hasOwnProperty.call(over, "widths") ? over.widths : null;
    const hay = (row.dataset.search || "").toLowerCase();
    if (state.search && !hay.includes(state.search)) return false;
    if (store !== "all" && (row.dataset.store || "") !== store) return false;
    if (part !== "all" && (row.dataset.part || "") !== part) return false;
    const viewPart = part || "Decks";
    if (specKeyActive("widths", viewPart) && !deckWidthAllowed(row, widths)) return false;
    for (let specIndex = 0; specIndex < SPEC_FACETS.length; specIndex++) {
        const facet = SPEC_FACETS[specIndex];
        if (!specKeyActive(facet.stateKey, viewPart)) continue;
        const selected = Object.prototype.hasOwnProperty.call(over, facet.stateKey) ? over[facet.stateKey] : state[facet.stateKey];
        if (!specAllowed(row, facet, selected)) return false;
    }
    if (brand !== "all" && !brandSame(row.dataset.brand, brand)) return false;
    if (specKeyActive("length", viewPart) && length !== "all" && (row.dataset.length || "") !== length) return false;
    if (specKeyActive("wheelbase", viewPart) && wheelbase !== "all" && (row.dataset.wheelbase || "") !== wheelbase) return false;
    const price = parseFloat(row.dataset.price);
    if (state.priceMin != null && !(price >= state.priceMin)) return false;
    if (state.priceMax != null && !(price <= state.priceMax)) return false;
    const discountMax = Object.prototype.hasOwnProperty.call(over, "discountMax") ? over.discountMax : state.discountMax;
    if (state.discountMin != null || discountMax != null) {
        if (row.dataset.discount === "") return false;
        const discount = parseFloat(row.dataset.discount);
        if (state.discountMin != null && discount < state.discountMin) return false;
        if (discountMax != null && discount > discountMax) return false;
    }
    const score = parseFloat(row.dataset.score);
    if (state.scoreMin != null && !(score >= state.scoreMin)) return false;
    if (state.scoreMax != null && !(score <= state.scoreMax)) return false;
    const watching = Object.prototype.hasOwnProperty.call(over, "watching") ? over.watching : state.watching;
    if (watching && row.dataset.starred !== "1") return false;
    const kinds = Object.prototype.hasOwnProperty.call(over, "kinds") ? over.kinds : state.kinds;
    if (!kindMatch(row, kinds)) return false;
    const highlights = Object.prototype.hasOwnProperty.call(over, "highlights") ? over.highlights : state.highlights;
    if (highlights && row.dataset.highlight !== "1") return false;
    const interval = over.interval != null ? over.interval : state.dropInterval;
    if (!dropInInterval(row, interval)) return false;
    if (state.cardNew && row.dataset.added !== "1") return false;
    if (state.cardDrop && row.dataset.drop !== "1") return false;
    if (state.cardLow && row.dataset.lowest !== "1") return false;
    const added = state.visitMode === "visit" ? row.dataset.visitNew : row.dataset.added;
    const drop = state.visitMode === "visit" ? row.dataset.visitDrop : row.dataset.drop;
    const low = state.visitMode === "visit" ? row.dataset.visitLow : row.dataset.hitlow;
    if (state.change === "new" && added !== "1") return false;
    if (state.change === "drop" && drop !== "1") return false;
    if (state.change === "lowest" && low !== "1") return false;
    // "removed" opens Recently gone. It does not hide current deals.
    return true;
}

function syncDetails() {
    indexDeals();
    detailById.forEach((detail, id) => {
        const row = rowById.get(id);
        const parentHidden = !row || row.classList.contains("filtered-out") || row.classList.contains("grouped-hide");
        const open = row && row.classList.contains("open");
        detail.hidden = parentHidden || !open;
    });
}

function applyGroupVisibility() {
    const board = document.getElementById("groupBoard");
    if (!board) return;
    if (!state.grouped) {
        board.hidden = true;
        dealRows().forEach(row => row.classList.remove("grouped-hide"));
        mirrorCardFlags();
        return;
    }
    board.hidden = false;
    const visible = new Set();
    dealRows().forEach(row => {
        if (row.dataset.group && !row.classList.contains("filtered-out")) {
            visible.add(row.dataset.group);
            row.classList.add("grouped-hide");
        } else {
            row.classList.remove("grouped-hide");
        }
    });
    board.querySelectorAll(".group-card").forEach(card => {
        card.hidden = !visible.has(card.dataset.key);
    });
    const empty = board.querySelector(".group-empty");
    if (empty) empty.hidden = visible.size !== 0;
    mirrorCardFlags();
}

function mirrorCardFlags() {
    dealRows().forEach(row => {
        const card = cardFor(row.dataset.id);
        if (!card) return;
        card.classList.toggle("filtered-out", row.classList.contains("filtered-out"));
        card.classList.toggle("grouped-hide", row.classList.contains("grouped-hide"));
    });
}

function showGone(on) {
    const gone = document.getElementById("goneSection");
    if (!gone) return;
    const content = gone.querySelector(".section-content");
    const header = gone.querySelector(".section-header");
    if (on) {
        if (content) content.classList.remove("collapsed");
        if (header) header.classList.remove("collapsed");
    }
}

let filterTimer = 0;

function queueFilters() {
    clearTimeout(filterTimer);
    filterTimer = setTimeout(applyFilters, 80);
}

function applyFilters() {
    matchMemo = new Map();
    readControls();
    dealRows().forEach(row => {
        row.classList.toggle("filtered-out", !rowMatches(row));
    });
    showGone(state.change === "removed");
    applySectionFilters();
    applyGroupVisibility();
    syncGroupOrder();
    syncDetails();
    paintCards();
    paintWidthChips();
    paintBrandFacet();
    paintFacetCounts();
    updateMoreCount();
    paintActiveChips();
    paintResultCount();
    syncUrl();
    paintViews();
    paintNav();
    syncDuals();
    matchMemo = null;
}

function paintKeepaCounts() {
    const intervalCounts = { all: 0, day: 0, week: 0, month: 0, quarter: 0 };
    const kindCounts = { new: 0, drop: 0, low: 0, back: 0, hot: 0, watch: 0, highlights: 0 };
    let categoryAll = 0;
    const categoryCounts = {};
    dealRows().forEach(row => {
        if (rowMatches(row, { interval: "all" })) {
            intervalCounts.all += 1;
            ["day", "week", "month", "quarter"].forEach(key => {
                if (dropInInterval(row, key)) intervalCounts[key] += 1;
            });
        }
        if (rowMatches(row, { kinds: [] })) {
            if (row.dataset.fresh === "1") kindCounts.new += 1;
            if (row.dataset.drop === "1") kindCounts.drop += 1;
            if (row.dataset.lowest === "1") kindCounts.low += 1;
            if (row.dataset.back === "1") kindCounts.back += 1;
            if (row.dataset.hot === "1") kindCounts.hot += 1;
        }
        if (row.dataset.starred === "1" && rowMatches(row, { watching: false })) kindCounts.watch += 1;
        if (row.dataset.highlight === "1" && rowMatches(row, { highlights: false })) kindCounts.highlights += 1;
        if (rowMatches(row, { part: "all" })) {
            categoryAll += 1;
            const part = row.dataset.part || "";
            if (part) categoryCounts[part] = (categoryCounts[part] || 0) + 1;
        }
    });
    document.querySelectorAll("#dropInterval [data-interval]").forEach(button => {
        const key = button.getAttribute("data-interval") || "all";
        const slot = button.querySelector(".facet-count");
        if (slot) slot.textContent = "(" + (intervalCounts[key] || 0) + ")";
        const on = (state.dropInterval || "all") === key;
        button.setAttribute("aria-pressed", on ? "true" : "false");
        button.classList.toggle("is-zero", key !== "all" && !(intervalCounts[key]));
    });
    document.querySelectorAll("#dealTypes [data-kind]").forEach(button => {
        const key = button.getAttribute("data-kind") || "";
        const slot = button.querySelector(".facet-count");
        if (slot) slot.textContent = "(" + (kindCounts[key] || 0) + ")";
        const on = key === "watch" ? !!state.watching : key === "highlights" ? !!state.highlights : (state.kinds || []).indexOf(key) >= 0;
        button.setAttribute("aria-pressed", on ? "true" : "false");
        button.classList.toggle("is-zero", !(kindCounts[key]));
    });
    document.querySelectorAll("#categoryStrip [data-part]").forEach(button => {
        const part = button.getAttribute("data-part") || "all";
        const count = part === "all" ? categoryAll : (categoryCounts[part] || 0);
        const slot = button.querySelector(".cat-count");
        if (slot) slot.textContent = String(count);
        button.setAttribute("aria-pressed", (state.part || "Decks") === part ? "true" : "false");
    });
}

function setDropInterval(key) {
    state.dropInterval = key === "all" || DROP_INTERVALS[key] ? key : "all";
    applyFilters();
}

function toggleDealType(kind) {
    if (kind === "watch") {
        toggleWatching();
        return;
    }
    if (kind === "highlights") {
        state.highlights = !state.highlights;
        applyFilters();
        return;
    }
    if (DEAL_KINDS.indexOf(kind) < 0) return;
    const selected = {};
    (state.kinds || []).forEach(item => { selected[item] = true; });
    if (selected[kind]) delete selected[kind];
    else selected[kind] = true;
    state.kinds = DEAL_KINDS.filter(item => selected[item]);
    applyFilters();
}

function syncDuals() {
    document.querySelectorAll(".dual").forEach(box => {
        const floor = Number(box.dataset.floor);
        const ceil = Number(box.dataset.ceil);
        const minInput = document.getElementById(box.dataset.minInput);
        const maxInput = document.getElementById(box.dataset.maxInput);
        const minRange = box.querySelector(".dual-min");
        const maxRange = box.querySelector(".dual-max");
        const readout = box.querySelector(".dual-readout");
        if (!minRange || !maxRange || !Number.isFinite(floor) || !Number.isFinite(ceil)) return;
        let lo = minInput && minInput.value !== "" ? Number(minInput.value) : floor;
        let hi = maxInput && maxInput.value !== "" ? Number(maxInput.value) : ceil;
        if (!Number.isFinite(lo)) lo = floor;
        if (!Number.isFinite(hi)) hi = ceil;
        lo = Math.min(ceil, Math.max(floor, lo));
        hi = Math.min(ceil, Math.max(floor, hi));
        if (lo > hi) lo = hi;
        minRange.value = String(lo);
        maxRange.value = String(hi);
        const prefix = box.dataset.prefix || "";
        const suffix = box.dataset.suffix || "";
        const minEmpty = !minInput || minInput.value === "";
        const maxEmpty = !maxInput || maxInput.value === "";
        const format = value => prefix + numText(value) + suffix;
        let text = box.dataset.any || "Any";
        if (!minEmpty || !maxEmpty) {
            text = (minEmpty ? "Any" : format(minInput.value)) + " – " + (maxEmpty ? "Any" : format(maxInput.value));
        }
        if (readout) readout.textContent = text;
        minRange.setAttribute("aria-valuetext", minEmpty ? "Any" : format(minInput.value));
        maxRange.setAttribute("aria-valuetext", maxEmpty ? "Any" : format(maxInput.value));
    });
}

function wireDuals() {
    document.querySelectorAll(".dual").forEach(box => {
        const minRange = box.querySelector(".dual-min");
        const maxRange = box.querySelector(".dual-max");
        if (!minRange || !maxRange) return;
        const applyRange = () => {
            const floor = Number(box.dataset.floor);
            const ceil = Number(box.dataset.ceil);
            const minInput = document.getElementById(box.dataset.minInput);
            const maxInput = document.getElementById(box.dataset.maxInput);
            let lo = Number(minRange.value);
            let hi = Number(maxRange.value);
            if (lo > hi) {
                if (document.activeElement === minRange) {
                    hi = lo;
                    maxRange.value = String(hi);
                } else {
                    lo = hi;
                    minRange.value = String(lo);
                }
            }
            if (minInput) minInput.value = lo <= floor ? "" : numText(lo);
            if (maxInput) maxInput.value = hi >= ceil ? "" : numText(hi);
            applyFilters();
        };
        minRange.addEventListener("input", applyRange);
        maxRange.addEventListener("input", applyRange);
    });
}

function paintOneCardStat(card) {
    const node = card ? card.querySelector(".avg-price") : null;
    if (!node) return;
    const days = typeof chartWindow === "number" ? chartWindow : 90;
    const item = (catalog().items || {})[card.dataset.id];
    const daily = item && Array.isArray(item.daily) ? item.daily : [];
    const points = clipDailyPrices(daily, days);
    if (!points.length) {
        node.hidden = true;
        return;
    }
    const sum = points.reduce((total, point) => total + Number(point[1]), 0);
    const average = sum / points.length;
    const now = parseFloat(card.dataset.price);
    const symbol = node.dataset.symbol || "$";
    if (Number.isFinite(now) && Math.abs(average - now) < 0.005) {
        node.hidden = true;
        return;
    }
    node.hidden = false;
    node.textContent = "Average: " + symbol + average.toFixed(2);
    node.dataset.statWindow = String(chartWindow);
}

function paintCardStats() {
    document.querySelectorAll("#cardGrid .deal-card").forEach(paintOneCardStat);
}

function paintResultCount() {
    const node = document.getElementById("statusCounts");
    if (!node) return;
    let count = 0;
    dealRows().forEach(row => {
        if (!row.classList.contains("filtered-out") && !row.classList.contains("grouped-hide")) count += 1;
    });
    node.textContent = count + (count === 1 ? " deal" : " deals");
}

function filterProducts() {
    applyFilters();
}

function paintQuickRow(groupId, attr, counts, current) {
    let total = 0;
    Object.keys(counts).forEach(key => { total += counts[key] || 0; });
    document.querySelectorAll("#" + groupId + " .quick-chip").forEach(node => {
        const value = node.getAttribute(attr) || "";
        const count = value === "all" ? total : (counts[value] || 0);
        const slot = node.querySelector(".quick-count");
        if (slot) slot.textContent = String(count);
        const on = value === current;
        node.classList.toggle("active", on);
        node.setAttribute("aria-pressed", on ? "true" : "false");
        node.classList.toggle("is-zero", count === 0);
        node.setAttribute("data-count", String(count));
    });
}

function nextNavOverflow(clusters) {
    const groups = clusters || [];
    for (let i = groups.length - 1; i >= 0; i -= 1) {
        const chips = groups[i].chips || [];
        if (chips.length <= 1) continue;
        for (let j = chips.length - 1; j >= 0; j -= 1) {
            const chip = chips[j];
            if (!chip || chip.pressed || chip.value === "all") continue;
            return { cluster: i, index: j };
        }
    }
    return null;
}

function navClusters() {
    return ["storeFilters", "partFilters"].map(id => {
        const root = document.getElementById(id);
        if (!root) return null;
        const row = root.querySelector(".quick-row");
        const menu = root.querySelector(".more-menu");
        const list = root.querySelector(".more-list");
        if (!row || !menu || !list) return null;
        return { root: root, row: row, menu: menu, list: list };
    }).filter(Boolean);
}

function restoreNavHomes(cluster) {
    const chips = Array.from(cluster.root.querySelectorAll(".quick-chip"));
    chips.sort((a, b) => Number(a.getAttribute("data-order") || 0) - Number(b.getAttribute("data-order") || 0));
    chips.forEach(chip => {
        if (chip.getAttribute("data-home") === "more") cluster.list.appendChild(chip);
        else cluster.row.insertBefore(chip, cluster.menu);
    });
}

function syncNavMore(cluster) {
    const count = cluster.list.querySelectorAll(":scope > .quick-chip").length;
    const toggle = cluster.menu.querySelector(".more-toggle");
    if (!count) {
        cluster.menu.hidden = true;
        cluster.list.hidden = true;
        if (toggle) toggle.setAttribute("aria-expanded", "false");
        return;
    }
    cluster.menu.hidden = false;
}

function pullPressedNavChip(cluster) {
    const pressed = cluster.list.querySelector('.quick-chip[aria-pressed="true"]');
    if (pressed) cluster.row.insertBefore(pressed, cluster.menu);
}

let navFitLock = false;
let navFitQueued = false;

function scheduleNavFit() {
    if (navFitQueued) return;
    navFitQueued = true;
    requestAnimationFrame(() => {
        navFitQueued = false;
        fitNavPills();
    });
}

function fitNavPills() {
    const bar = document.getElementById("navPills");
    if (!bar || navFitLock) return;
    const clusters = navClusters();
    if (!clusters.length) return;
    navFitLock = true;
    try {
        clusters.forEach(restoreNavHomes);
        clusters.forEach(syncNavMore);
        const settle = () => {
            let guard = 0;
            const limit = () => {
                const viewport = document.documentElement.clientWidth || bar.clientWidth;
                return Math.min(bar.clientWidth || viewport, viewport);
            };
            while (limit() > 0 && bar.scrollWidth > limit() + 1 && guard < 40) {
                guard += 1;
                const choice = nextNavOverflow(clusters.map(cluster => ({
                    chips: Array.from(cluster.row.querySelectorAll(":scope > .quick-chip")).map(chip => ({
                        value: chip.getAttribute("data-store") || chip.getAttribute("data-part") || "",
                        pressed: chip.getAttribute("aria-pressed") === "true",
                    })),
                })));
                if (!choice) return;
                const cluster = clusters[choice.cluster];
                const chip = cluster.row.querySelectorAll(":scope > .quick-chip")[choice.index];
                if (!chip) return;
                cluster.list.appendChild(chip);
                syncNavMore(cluster);
            }
        };
        settle();
        clusters.forEach(pullPressedNavChip);
        clusters.forEach(syncNavMore);
        settle();
    } finally {
        navFitLock = false;
    }
}

function paintTypeHint() {
    const hint = document.getElementById("typeHint");
    if (hint) hint.hidden = state.part !== "all";
}

function filterByStore(store) {
    state.store = store || "all";
    const select = document.getElementById("storeSelect");
    if (select) select.value = state.store;
    setPressed("#storeFilters [data-store]", "data-store", state.store);
    applyFilters();
}

function filterByPart(part) {
    const next = part || "all";
    const changed = next !== (state.part || "all");
    state.part = next;
    const select = document.getElementById("partSelect");
    if (select) select.value = state.part;
    setPressed("#partFilters [data-part]", "data-part", state.part);
    syncTypeSections(changed);
    applyFilters();
}

function toggleWidthRange(id) {
    if (!id || id === "all") {
        state.widths = [];
    } else {
        const selected = {};
        (state.widths || []).forEach(item => { selected[item] = true; });
        if (selected[id]) delete selected[id];
        else selected[id] = true;
        state.widths = orderedWidths(Object.keys(selected));
    }
    paintWidthChips();
    applyFilters();
}

function toggleCard(kind, store) {
    if (kind === "new") state.cardNew = !state.cardNew;
    else if (kind === "drop") state.cardDrop = !state.cardDrop;
    else if (kind === "lowest") state.cardLow = !state.cardLow;
    else if (kind === "store") {
        state.store = state.store === store ? "all" : store;
        const select = document.getElementById("storeSelect");
        if (select) select.value = state.store;
        setPressed("#storeFilters [data-store]", "data-store", state.store);
    } else if (kind === "clear") {
        state.cardNew = false;
        state.cardDrop = false;
        state.cardLow = false;
        state.store = "all";
        state.change = "all";
        const select = document.getElementById("storeSelect");
        if (select) select.value = "all";
        setPressed("#storeFilters [data-store]", "data-store", "all");
    }
    applyFilters();
}

function setChange(kind) {
    // Summary cards stay independent. Choosing a digest chip does not press them.
    if (!kind || kind === "all" || state.change === kind) state.change = "all";
    else state.change = kind;
    applyFilters();
    if (state.change === "removed") {
        const gone = document.getElementById("goneSection");
        if (gone) gone.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

const SORT_NUMERIC = { price: 1, original: 1, discount: 1, size: 1, days: 1, daysat: 1, score: 1, rank: 1, observations: 1 };

function defaultSortDir(key) {
    if (key === "price" || key === "rank" || key === "store" || key === "brand" || key === "size" || key === "daysat" || key === "name" || key === "part" || key === "stage") {
        return "asc";
    }
    return "desc";
}

function compareSort(a, b, key, direction) {
    if (key === "rank") return (parseFloat(a.dataset.rank) || 0) - (parseFloat(b.dataset.rank) || 0);
    const av = a.dataset[key];
    const bv = b.dataset[key];
    const aMissing = av === undefined || av === "";
    const bMissing = bv === undefined || bv === "";
    if (aMissing && bMissing) return 0;
    if (aMissing) return 1;
    if (bMissing) return -1;
    if (SORT_NUMERIC[key]) {
        const diff = parseFloat(av) - parseFloat(bv);
        return direction === "asc" ? diff : -diff;
    }
    const diff = String(av).localeCompare(String(bv));
    return direction === "asc" ? diff : -diff;
}

function sortBy(key, direction) {
    const tbody = document.querySelector("#mainTable tbody");
    if (!tbody) return;
    if (!direction) {
        if (state.sortKey === key) direction = state.sortDir === "asc" ? "desc" : "asc";
        else direction = defaultSortDir(key);
    }
    state.sortKey = key;
    state.sortDir = direction;
    const rows = Array.from(tbody.querySelectorAll(".deal-row"));
    rows.sort((a, b) => compareSort(a, b, key, direction));
    rows.forEach(row => {
        const detail = document.querySelector('.detail-row[data-for="' + row.dataset.id + '"]');
        tbody.appendChild(row);
        if (detail) tbody.appendChild(detail);
    });
    document.querySelectorAll("#mainTable [data-sort]").forEach(node => node.classList.remove("sorted"));
    const header = document.querySelector('#mainTable [data-sort="' + key + '"]');
    if (header) header.classList.add("sorted");
    mirrorSort(key, direction);
    syncCardOrder();
    syncUrl();
}

function syncCardOrder() {
    const grid = document.getElementById("cardGrid");
    const tbody = document.querySelector("#mainTable tbody");
    if (!grid || !tbody) return;
    // dealRows() is cached the first time it runs, which is the rank order
    // (new items, then score). Reading that cache put the cards back and
    // left a % off sort looking unsorted. The table body is the live order.
    tbody.querySelectorAll(".deal-row").forEach(row => {
        const card = cardFor(row.dataset.id);
        if (card) grid.appendChild(card);
    });
    syncGroupOrder();
}

function syncGroupOrder() {
    const board = document.getElementById("groupBoard");
    if (!board) return;
    const cards = Array.from(board.querySelectorAll(".group-card"));
    if (cards.length < 2) return;
    const key = state.sortKey || "rank";
    const direction = state.sortDir || "asc";
    const members = new Map();
    document.querySelectorAll("#mainTable tbody .deal-row").forEach(row => {
        const group = row.dataset.group || "";
        if (!group || row.classList.contains("filtered-out")) return;
        if (!members.has(group)) members.set(group, []);
        members.get(group).push(row);
    });
    function winner(group) {
        const list = members.get(group);
        if (!list || !list.length) return null;
        let best = list[0];
        for (let i = 1; i < list.length; i++) {
            if (compareSort(list[i], best, key, direction) < 0) best = list[i];
        }
        return best;
    }
    cards.sort((a, b) => {
        const left = winner(a.dataset.key || "");
        const right = winner(b.dataset.key || "");
        if (!left && !right) return 0;
        if (!left) return 1;
        if (!right) return -1;
        return compareSort(left, right, key, direction);
    });
    cards.forEach(card => board.appendChild(card));
}

function sortTable() {
    sortBy("price");
}

function sortSection(tableId, key, direction) {
    const table = document.getElementById(tableId);
    const tbody = table ? table.querySelector("tbody") : null;
    if (!tbody) return;
    const currentKey = table.getAttribute("data-sort-key") || "";
    const currentDir = table.getAttribute("data-sort-dir") || "asc";
    if (!direction) {
        direction = currentKey === key ? (currentDir === "asc" ? "desc" : "asc") : defaultSortDir(key);
    }
    table.setAttribute("data-sort-key", key);
    table.setAttribute("data-sort-dir", direction);
    const rows = Array.from(tbody.querySelectorAll("tr"));
    rows.sort((a, b) => compareSort(a, b, key, direction));
    rows.forEach(row => tbody.appendChild(row));
    table.querySelectorAll("[data-sort]").forEach(node => {
        const on = node.getAttribute("data-sort") === key;
        node.classList.toggle("sorted", on);
        if (on) node.setAttribute("aria-sort", direction === "asc" ? "ascending" : "descending");
        else node.removeAttribute("aria-sort");
    });
}

function sectionMatches(row) {
    const hay = (row.dataset.search || "").toLowerCase();
    if (state.search && !hay.includes(state.search)) return false;
    if (state.store !== "all" && (row.dataset.store || "") !== state.store) return false;
    if (state.part !== "all" && (row.dataset.part || "") !== state.part) return false;
    if (state.brand !== "all" && !brandSame(row.dataset.brand, state.brand)) return false;
    const price = parseFloat(row.dataset.price);
    if (state.priceMin != null && !(price >= state.priceMin)) return false;
    if (state.priceMax != null && !(price <= state.priceMax)) return false;
    return true;
}

function applySectionFilters() {
    ["goneSection", "atlSection"].forEach(id => {
        const section = document.getElementById(id);
        if (!section) return;
        const rows = Array.from(section.querySelectorAll("tbody tr"));
        let shown = 0;
        rows.forEach(row => {
            const hide = !sectionMatches(row);
            row.classList.toggle("filtered-out", hide);
            if (!hide) shown += 1;
        });
        const badge = section.querySelector("h2 .badge");
        if (badge) badge.textContent = String(shown);
    });
}

function mirrorSort(key, direction) {
    const select = document.getElementById("sortSelect");
    if (!select) return;
    let value = "";
    if (key === "price" && direction === "desc") value = "price-desc";
    else if (key === "price" && direction === "asc") value = "price";
    else if (select.querySelector('option[value="' + key + '"]')) value = key;
    if (value) select.value = value;
}

function applySortChoice() {
    const choice = document.getElementById("sortSelect");
    if (!choice) return;
    const value = choice.value;
    if (value === "rank") sortBy("rank", "asc");
    else if (value === "score") sortBy("score", "desc");
    else if (value === "price") sortBy("price", "asc");
    else if (value === "price-desc") sortBy("price", "desc");
    else if (value === "original") sortBy("original", "asc");
    else if (value === "discount") sortBy("discount", "desc");
    else if (value === "size") sortBy("size", "asc");
    else if (value === "store") sortBy("store", "asc");
    else if (value === "brand") sortBy("brand", "asc");
    else if (value === "days") sortBy("days", "desc");
    else if (value === "daysat") sortBy("daysat", "asc");
}

function toggleSection(header) {
    header.classList.toggle("collapsed");
    const content = header.nextElementSibling;
    if (content) content.classList.toggle("collapsed");
}

function toggleDetail(row) {
    row.classList.toggle("open");
    syncDetails();
}

function applyStars() {
    const stars = starSet();
    document.querySelectorAll(".deal-row, .deal-card").forEach(row => {
        const on = stars.has(row.dataset.url);
        row.dataset.starred = on ? "1" : "0";
        const button = row.querySelector(".star");
        if (!button) return;
        button.classList.toggle("on", on);
        button.setAttribute("aria-pressed", on ? "true" : "false");
        button.textContent = on ? "★" : "☆";
    });
}

function toggleStar(button) {
    const row = button.closest(".deal-row, .deal-card");
    if (!row) return;
    const stars = starSet();
    if (stars.has(row.dataset.url)) stars.delete(row.dataset.url);
    else stars.add(row.dataset.url);
    writeJson(STAR_KEY, Array.from(stars));
    applyStars();
    applyFilters();
}

function plural(count, singular, pluralText) {
    return count + " " + (count === 1 ? singular : pluralText);
}

function updateChangeLine() {
    const prefix = document.getElementById("changePrefix");
    const note = document.getElementById("visitNote");
    let added = 0;
    let drop = 0;
    let low = 0;
    let gone = 0;
    if (state.visitMode === "visit") {
        dealRows().forEach(row => {
            if (row.dataset.visitNew === "1") added += 1;
            if (row.dataset.visitDrop === "1") drop += 1;
            if (row.dataset.visitLow === "1") low += 1;
        });
        gone = visitGone.length;
        if (prefix) prefix.textContent = "Since your last visit:";
    } else {
        const line = document.getElementById("changeLine");
        added = line ? parseInt(line.dataset.new || "0", 10) : 0;
        drop = line ? parseInt(line.dataset.drops || "0", 10) : 0;
        low = line ? parseInt(line.dataset.lows || "0", 10) : 0;
        gone = line ? parseInt(line.dataset.gone || "0", 10) : 0;
        if (prefix) prefix.textContent = "Since yesterday:";
    }
    const map = {
        btnNew: "New " + added,
        btnDrop: "Price drops " + drop,
        btnLow: "Hit lowest " + low,
        btnGone: "Disappeared " + gone
    };
    Object.keys(map).forEach(id => {
        const node = document.getElementById(id);
        if (node) node.textContent = map[id];
    });
    if (note) note.hidden = state.visitMode !== "visit" || !note.dataset.message;
}

function setVisitMode(mode) {
    state.visitMode = mode === "visit" ? "visit" : "yesterday";
    const yesterday = document.getElementById("modeYesterday");
    const visit = document.getElementById("modeVisit");
    if (yesterday) yesterday.setAttribute("aria-pressed", state.visitMode === "yesterday" ? "true" : "false");
    if (visit) visit.setAttribute("aria-pressed", state.visitMode === "visit" ? "true" : "false");
    const baseline = document.getElementById("baselineSelect");
    if (baseline) baseline.value = state.visitMode;
    updateChangeLine();
    applyFilters();
}

function prepareVisit() {
    // The saved snapshot is only the last-visit baseline for digest counts.
    // It is not a filter, and it is not restored into state.change.
    const data = catalog();
    const previous = readJson(SNAP_KEY, null);
    const current = {};
    const gone = [];
    dealRows().forEach(row => {
        current[row.dataset.url] = {
            price: parseFloat(row.dataset.price),
            name: row.dataset.name || "",
            store: row.dataset.store || "",
            lowest: row.dataset.lowest || "0"
        };
    });
    const note = document.getElementById("visitNote");
    if (!previous || !previous.items) {
        dealRows().forEach(row => {
            row.dataset.visitNew = row.dataset.added || "0";
            row.dataset.visitDrop = row.dataset.drop || "0";
            row.dataset.visitLow = row.dataset.hitlow || "0";
        });
        visitGone = [];
        if (note) {
            note.dataset.message = "1";
            note.hidden = true;
            note.textContent = "First visit on this browser. This comparison matches since yesterday. The next visit compares against this scan.";
        }
    } else {
        dealRows().forEach(row => {
            const prior = previous.items[row.dataset.url];
            const price = parseFloat(row.dataset.price);
            if (!prior) {
                row.dataset.visitNew = "1";
                row.dataset.visitDrop = "0";
                row.dataset.visitLow = row.dataset.lowest === "1" ? "1" : "0";
            } else {
                row.dataset.visitNew = "0";
                row.dataset.visitDrop = price < prior.price - 0.001 ? "1" : "0";
                row.dataset.visitLow = row.dataset.lowest === "1" && price < prior.price - 0.001 ? "1" : "0";
            }
        });
        const liveNames = {};
        dealRows().forEach(row => {
            const name = (row.dataset.name || "").trim().toLowerCase();
            if (name) liveNames[name] = true;
        });
        Object.keys(previous.items).forEach(url => {
            if (!current[url]) gone.push(previous.items[url]);
        });
        visitGone = gone;
        if (note) {
            note.dataset.message = "1";
            note.hidden = true;
            const when = previous.at ? " Last visit " + previous.at + "." : "";
            const missing = gone.filter(item => {
                const name = (item.name || "").trim().toLowerCase();
                return name && !liveNames[name];
            });
            note.textContent = missing.length
                ? "Left since that visit: " + missing.map(item => item.name).slice(0, 8).join(", ") + when
                : "Nothing in the saved visit is missing from this scan." + when;
        }
    }
    writeJson(SNAP_KEY, { at: data.generated || "", items: current });
}

function openDrawer(id) {
    const item = (catalog().items || {})[id];
    const drawer = document.getElementById("priceDrawer");
    if (!drawer || !item) return;
    const series = item.series || [];
    const chain = series.map(point => "$" + Number(point[1]).toFixed(2)).join(" → ");
    document.getElementById("drawerTitle").textContent = item.name || "Price history";
    document.getElementById("drawerChain").textContent = chain || "No tracked prices yet.";
    const list = document.getElementById("drawerList");
    list.innerHTML = "";
    series.forEach(point => {
        const li = document.createElement("li");
        const date = document.createElement("span");
        const price = document.createElement("strong");
        date.textContent = point[0];
        price.textContent = "$" + Number(point[1]).toFixed(2);
        li.appendChild(date);
        li.appendChild(price);
        list.appendChild(li);
    });
    const link = document.getElementById("drawerLink");
    if (item.url) {
        link.hidden = false;
        link.href = item.url;
        link.textContent = "Open product page";
    } else {
        link.hidden = true;
    }
    drawer.hidden = false;
}

function closeDrawer() {
    const drawer = document.getElementById("priceDrawer");
    if (drawer) drawer.hidden = true;
}

function toggleGrouped() {
    state.grouped = !state.grouped;
    const button = document.getElementById("groupToggle");
    if (button) button.setAttribute("aria-pressed", state.grouped ? "true" : "false");
    applyFilters();
}

function toggleWatching() {
    state.watching = !state.watching;
    const button = document.getElementById("watchingToggle");
    if (button) button.setAttribute("aria-pressed", state.watching ? "true" : "false");
    applyFilters();
}

function toggleStats() {
    const panel = document.getElementById("statsPanel");
    const button = document.getElementById("statsToggle");
    if (!panel) return;
    panel.hidden = !panel.hidden;
    if (button) button.setAttribute("aria-pressed", panel.hidden ? "false" : "true");
    if (!panel.hidden) panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function clearFilters() {
    state = {
        store: "all",
        part: "Decks",
        brand: "all",
        length: "all",
        wheelbase: "all",
        watching: false,
        cardNew: false,
        cardDrop: false,
        cardLow: false,
        change: "all",
        grouped: false,
        dropInterval: "all",
        kinds: [],
        highlights: false,
        diameters: [],
        duros: [],
        shapes: [],
        truckSizes: [],
        truckHeights: [],
        constructions: [],
        abecs: [],
        shoeSizes: [],
        visitMode: "yesterday",
        sortKey: "rank",
        sortDir: "asc",
        search: "",
        widths: []
    };
    navMode = "deals";
    const search = document.getElementById("searchInput");
    if (search) search.value = "";
    ["priceMin", "priceMax", "discountMin", "discountMax", "scoreMin", "scoreMax"].forEach(id => {
        const node = document.getElementById(id);
        if (node) node.value = "";
    });
    ["storeSelect", "brandSelect", "lengthSelect", "wheelbaseSelect"].forEach(id => {
        const node = document.getElementById(id);
        if (node) node.value = "all";
    });
    const partSelect = document.getElementById("partSelect");
    if (partSelect) partSelect.value = "Decks";
    const sort = document.getElementById("sortSelect");
    if (sort) sort.value = "rank";
    const watching = document.getElementById("watchingToggle");
    if (watching) watching.setAttribute("aria-pressed", "false");
    const grouped = document.getElementById("groupToggle");
    if (grouped) grouped.setAttribute("aria-pressed", "false");
    const baseline = document.getElementById("baselineSelect");
    if (baseline) baseline.value = "yesterday";
    const yesterday = document.getElementById("modeYesterday");
    const visit = document.getElementById("modeVisit");
    if (yesterday) yesterday.setAttribute("aria-pressed", "true");
    if (visit) visit.setAttribute("aria-pressed", "false");
    const panel = document.getElementById("statsPanel");
    const statsToggle = document.getElementById("statsToggle");
    if (panel) panel.hidden = true;
    if (statsToggle) statsToggle.setAttribute("aria-pressed", "false");
    const brandSearch = document.getElementById("brandSearch");
    if (brandSearch) brandSearch.value = "";
    filterBrandList("");
    setPressed("#storeFilters [data-store]", "data-store", "all");
    setPressed("#partFilters [data-part]", "data-part", "Decks");
    paintWidthChips();
    syncTypeSections(false);
    sortBy("rank", "asc");
    applyFilters();
    updateChangeLine();
    scrollResultsToTop();
}

function scrollResultsToTop() {
    window.scrollTo(0, 0);
    const board = document.querySelector(".board");
    if (board) board.scrollTop = 0;
    const side = document.querySelector(".rail .sidebar");
    if (side) side.scrollTop = 0;
}

function measureBar() {
    const bar = document.getElementById("stickyBar") || document.querySelector(".sticky-bar");
    if (!bar) return;
    document.documentElement.style.setProperty("--stick-top", Math.ceil(bar.offsetHeight) + "px");
}

function parseScan(raw) {
    if (!raw) return NaN;
    if (raw.indexOf("T") >= 0) return Date.parse(raw);
    return Date.parse(raw.replace(" ", "T") + "Z");
}

function formatEt(date) {
    try {
        const parts = new Intl.DateTimeFormat("en-US", {
            timeZone: "America/New_York",
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "numeric",
            minute: "2-digit",
            second: "2-digit",
            hour12: true
        }).formatToParts(date);
        const get = type => {
            const found = parts.find(part => part.type === type);
            return found ? found.value : "";
        };
        return get("month") + " " + get("day") + ", " + get("year") + " " + get("hour") + ":" + get("minute") + ":" + get("second") + " " + get("dayPeriod") + " ET";
    } catch (err) {
        return "";
    }
}

function updateAgo() {
    const node = document.getElementById("lastScan");
    if (!node) return;
    const raw = node.getAttribute("datetime") || "";
    const parsed = parseScan(raw);
    const exact = document.getElementById("scanExact");
    if (Number.isFinite(parsed)) {
        const label = formatEt(new Date(parsed));
        if (label) {
            node.title = label;
            if (exact) exact.textContent = label;
        }
    }
    if (!Number.isFinite(parsed)) return;
    const seconds = Math.max(0, (Date.now() - parsed) / 1000);
    let label = raw;
    if (seconds < 90) label = "just now";
    else if (seconds < 5400) label = Math.round(seconds / 60) + " minutes ago";
    else if (seconds < 129600) label = Math.round(seconds / 3600) + " hours ago";
    else label = Math.round(seconds / 86400) + " days ago";
    node.textContent = label;
    updateFreshness();
}

function updateBanners() {
    document.querySelectorAll(".sale-banner").forEach(node => {
        const parsed = parseScan(node.getAttribute("data-at") || "");
        const slot = node.querySelector(".ago");
        if (!slot || !Number.isFinite(parsed)) return;
        const hours = Math.max(0, (Date.now() - parsed) / 3600000);
        if (hours < 1) slot.textContent = "under an hour ago";
        else {
            const whole = Math.floor(hours);
            slot.textContent = whole + (whole === 1 ? " hour ago" : " hours ago");
        }
    });
}

function slugStore(value) {
    const key = String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    return {
        zumiez: "Zumiez",
        skatewarehouse: "SkateWarehouse",
        ccs: "CCS",
        tactics: "Tactics",
        skatedeluxe: "Skate Deluxe",
        muirskate: "Muir Skate"
    }[key] || "";
}

function slugType(value) {
    const key = String(value || "").trim().toLowerCase();
    if (key === "all") return "all";
    return {
        deck: "Decks",
        decks: "Decks",
        wheel: "Wheels",
        wheels: "Wheels",
        truck: "Trucks",
        trucks: "Trucks",
        bearing: "Bearings",
        bearings: "Bearings",
        sneaker: "Sneakers",
        sneakers: "Sneakers",
        accessory: "Accessories",
        accessories: "Accessories"
    }[key] || "";
}

function storeSlug(name) {
    return {
        Zumiez: "zumiez",
        SkateWarehouse: "skatewarehouse",
        CCS: "ccs",
        Tactics: "tactics",
        "Skate Deluxe": "skatedeluxe",
        "Muir Skate": "muirskate"
    }[name] || "";
}

function typeSlug(name) {
    return {
        Decks: "deck",
        Wheels: "wheel",
        Trucks: "truck",
        Bearings: "bearing",
        Sneakers: "sneaker",
        Accessories: "accessory"
    }[name] || "";
}

function flagOn(value) {
    return ["1", "true", "yes", "on"].indexOf(String(value || "").toLowerCase()) >= 0;
}

function decodeQuery(query) {
    const stateOut = {
        q: "",
        store: "all",
        part: "Decks",
        widths: [],
        brand: "all",
        min: null,
        max: null,
        discount: null,
        discountmax: null,
        scoremin: null,
        scoremax: null,
        length: "all",
        wheelbase: "all",
        sort: "rank",
        change: "all",
        watching: false,
        low: false,
        added: false,
        dropped: false,
        grouped: false,
        interval: "all",
        kinds: [],
        highlights: false,
        diameters: [],
        duros: [],
        shapes: [],
        truckSizes: [],
        truckHeights: [],
        constructions: [],
        abecs: [],
        shoeSizes: []
    };
    const text = String(query || "").replace(/^\?/, "");
    if (!text) return stateOut;
    const params = new URLSearchParams(text);
    params.forEach((value, key) => {
        key = String(key || "").toLowerCase();
        if (key === "q") stateOut.q = value.trim();
        else if (key === "store") {
            const store = slugStore(value);
            if (store) stateOut.store = store;
        } else if (key === "type") {
            const part = slugType(value);
            if (part) stateOut.part = part;
        } else if (key === "width") {
            stateOut.widths = parseWidthParam(value);
        } else if (key === "brand" && value.trim()) stateOut.brand = value.trim();
        else if (key === "min") stateOut.min = Number(value);
        else if (key === "max") stateOut.max = Number(value);
        else if (key === "discount") stateOut.discount = Number(value);
        else if (key === "discountmax") stateOut.discountmax = Number(value);
        else if (key === "scoremin") stateOut.scoremin = Number(value);
        else if (key === "scoremax") stateOut.scoremax = Number(value);
        else if (key === "length" && value && value !== "all") stateOut.length = value;
        else if (key === "wheelbase" && value && value !== "all") stateOut.wheelbase = value;
        else if (key === "sort" && ["rank", "score", "price", "price-desc", "original", "discount", "size", "store", "brand", "days", "daysat"].indexOf(value) >= 0) {
            stateOut.sort = value;
        } else if (key === "change" && ["new", "drop", "lowest", "removed"].indexOf(value) >= 0) {
            stateOut.change = value;
        } else if (key === "watching") stateOut.watching = flagOn(value);
        else if (key === "low") stateOut.low = flagOn(value);
        else if (key === "added") stateOut.added = flagOn(value);
        else if (key === "dropped") stateOut.dropped = flagOn(value);
        else if (key === "group") stateOut.grouped = flagOn(value);
        else if (key === "interval" && DROP_INTERVALS[String(value || "").toLowerCase()]) stateOut.interval = String(value).toLowerCase();
        else if (key === "kinds") {
            const chosen = {};
            String(value || "").split(",").forEach(token => {
                const kind = token.trim().toLowerCase();
                if (DEAL_KINDS.indexOf(kind) >= 0) chosen[kind] = true;
            });
            stateOut.kinds = DEAL_KINDS.filter(kind => chosen[kind]);
        } else if (key === "highlights") stateOut.highlights = flagOn(value);
        else if (key === "diameter") stateOut.diameters = orderSpecValues("diameters", String(value || "").split(","));
        else if (key === "duro") stateOut.duros = orderSpecValues("duros", String(value || "").split(","));
        else if (key === "shape") stateOut.shapes = orderSpecValues("shapes", String(value || "").split(","));
        else if (key === "trucksize") stateOut.truckSizes = orderSpecValues("truckSizes", String(value || "").split(","));
        else if (key === "truckheight") stateOut.truckHeights = orderSpecValues("truckHeights", String(value || "").split(","));
        else if (key === "construction") stateOut.constructions = orderSpecValues("constructions", String(value || "").split(","));
        else if (key === "abec") stateOut.abecs = orderSpecValues("abecs", String(value || "").split(","));
        else if (key === "shoesize") stateOut.shoeSizes = orderSpecValues("shoeSizes", String(value || "").split(","));
    });
    ["min", "max", "discount", "discountmax", "scoremin", "scoremax"].forEach(key => {
        if (!Number.isFinite(stateOut[key])) stateOut[key] = null;
    });
    return stateOut;
}

function encodeState(snapshot) {
    const params = new URLSearchParams();
    function add(key, value) {
        if (value == null) return;
        const text = String(value).trim();
        if (!text || text === "all") return;
        params.set(key, text);
    }
    add("q", snapshot.q || "");
    if (snapshot.store && snapshot.store !== "all") add("store", storeSlug(snapshot.store));
    // Missing type is Decks and stays out of the URL. All has to be written
    // with set(), because add() drops a bare "all".
    if (snapshot.part === "all") params.set("type", "all");
    else if (snapshot.part && snapshot.part !== "Decks") add("type", typeSlug(snapshot.part));
    const widths = orderedWidths(snapshot.widths || []);
    if (widths.length) add("width", widths.join(","));
    add("brand", snapshot.brand || "");
    if (snapshot.min != null) add("min", numText(snapshot.min));
    if (snapshot.max != null) add("max", numText(snapshot.max));
    if (snapshot.discount != null) add("discount", numText(snapshot.discount));
    if (snapshot.discountmax != null) add("discountmax", numText(snapshot.discountmax));
    if (snapshot.scoremin != null) add("scoremin", numText(snapshot.scoremin));
    if (snapshot.scoremax != null) add("scoremax", numText(snapshot.scoremax));
    add("length", snapshot.length || "");
    add("wheelbase", snapshot.wheelbase || "");
    if (snapshot.sort && snapshot.sort !== "rank") add("sort", snapshot.sort);
    if (["new", "drop", "lowest", "removed"].indexOf(snapshot.change) >= 0) add("change", snapshot.change);
    if (snapshot.watching) add("watching", "1");
    if (snapshot.low && snapshot.change !== "lowest") add("low", "1");
    if (snapshot.added && snapshot.change !== "new") add("added", "1");
    if (snapshot.dropped && snapshot.change !== "drop") add("dropped", "1");
    if (snapshot.grouped) add("group", "1");
    if (snapshot.interval && DROP_INTERVALS[snapshot.interval]) add("interval", snapshot.interval);
    const kinds = DEAL_KINDS.filter(kind => (snapshot.kinds || []).indexOf(kind) >= 0);
    if (kinds.length) add("kinds", kinds.join(","));
    if (snapshot.highlights) add("highlights", "1");
    const diameters = orderSpecValues("diameters", snapshot.diameters || []);
    if (diameters.length) add("diameter", diameters.join(","));
    const duros = orderSpecValues("duros", snapshot.duros || []);
    if (duros.length) add("duro", duros.join(","));
    const shapes = orderSpecValues("shapes", snapshot.shapes || []);
    if (shapes.length) add("shape", shapes.join(","));
    const truckSizes = orderSpecValues("truckSizes", snapshot.truckSizes || []);
    if (truckSizes.length) add("trucksize", truckSizes.join(","));
    const truckHeights = orderSpecValues("truckHeights", snapshot.truckHeights || []);
    if (truckHeights.length) add("truckheight", truckHeights.join(","));
    const constructions = orderSpecValues("constructions", snapshot.constructions || []);
    if (constructions.length) add("construction", constructions.join(","));
    const abecs = orderSpecValues("abecs", snapshot.abecs || []);
    if (abecs.length) add("abec", abecs.join(","));
    const shoeSizes = orderSpecValues("shoeSizes", snapshot.shoeSizes || []);
    if (shoeSizes.length) add("shoesize", shoeSizes.join(","));
    return params.toString();
}

function captureState() {
    readControls();
    const sort = document.getElementById("sortSelect");
    return {
        q: (document.getElementById("searchInput") || {}).value || "",
        store: state.store,
        part: state.part,
        widths: (state.widths || []).slice(),
        brand: state.brand,
        min: state.priceMin,
        max: state.priceMax,
        discount: state.discountMin,
        discountmax: state.discountMax,
        scoremin: state.scoreMin,
        scoremax: state.scoreMax,
        length: state.length,
        wheelbase: state.wheelbase,
        sort: sort ? sort.value : "rank",
        change: state.change,
        watching: state.watching,
        low: state.cardLow,
        added: state.cardNew,
        dropped: state.cardDrop,
        grouped: state.grouped,
        interval: state.dropInterval || "all",
        kinds: (state.kinds || []).slice(),
        highlights: !!state.highlights,
        diameters: (state.diameters || []).slice(),
        duros: (state.duros || []).slice(),
        shapes: (state.shapes || []).slice(),
        truckSizes: (state.truckSizes || []).slice(),
        truckHeights: (state.truckHeights || []).slice(),
        constructions: (state.constructions || []).slice(),
        abecs: (state.abecs || []).slice(),
        shoeSizes: (state.shoeSizes || []).slice()
    };
}

function brandSame(a, b) {
    return String(a || "").toLowerCase() === String(b || "").toLowerCase();
}

function setSelect(id, value) {
    const node = document.getElementById(id);
    if (!node) return;
    const options = Array.from(node.options || []);
    let match = options.find(option => option.value === value);
    if (!match && id === "brandSelect" && value) {
        match = options.find(option => brandSame(option.value, value));
    }
    if (match) node.value = match.value;
    else node.value = "all";
}

function writeControls(snapshot) {
    const search = document.getElementById("searchInput");
    if (search) search.value = snapshot.q || "";
    setSelect("storeSelect", snapshot.store || "all");
    setSelect("partSelect", snapshot.part || "Decks");
    setSelect("brandSelect", snapshot.brand || "all");
    const chosenBrand = document.getElementById("brandSelect");
    setSelect("lengthSelect", snapshot.length || "all");
    setSelect("wheelbaseSelect", snapshot.wheelbase || "all");
    setSelect("sortSelect", snapshot.sort || "rank");
    const fill = (id, value) => {
        const node = document.getElementById(id);
        if (node) node.value = value == null || !Number.isFinite(Number(value)) ? "" : numText(value);
    };
    fill("priceMin", snapshot.min);
    fill("priceMax", snapshot.max);
    fill("discountMin", snapshot.discount);
    fill("discountMax", snapshot.discountmax);
    fill("scoreMin", snapshot.scoremin);
    fill("scoreMax", snapshot.scoremax);
    const partChanged = (snapshot.part || "Decks") !== (state.part || "Decks");
    state.store = snapshot.store || "all";
    state.part = snapshot.part || "Decks";
    state.widths = orderedWidths(snapshot.widths || []);
    state.brand = chosenBrand ? (chosenBrand.value || "all") : (snapshot.brand || "all");
    state.length = snapshot.length || "all";
    state.wheelbase = snapshot.wheelbase || "all";
    state.change = snapshot.change || "all";
    state.watching = !!snapshot.watching;
    state.grouped = !!snapshot.grouped;
    // Card flags come only from added/dropped/low. A change= param must not
    // also turn a summary card on, and a card param must not select a digest chip.
    state.cardLow = !!snapshot.low;
    state.cardNew = !!snapshot.added;
    state.cardDrop = !!snapshot.dropped;
    state.dropInterval = snapshot.interval && DROP_INTERVALS[snapshot.interval] ? snapshot.interval : "all";
    state.kinds = DEAL_KINDS.filter(kind => (snapshot.kinds || []).indexOf(kind) >= 0);
    state.highlights = !!snapshot.highlights;
    state.diameters = orderSpecValues("diameters", snapshot.diameters || []);
    state.duros = orderSpecValues("duros", snapshot.duros || []);
    state.shapes = orderSpecValues("shapes", snapshot.shapes || []);
    state.truckSizes = orderSpecValues("truckSizes", snapshot.truckSizes || []);
    state.truckHeights = orderSpecValues("truckHeights", snapshot.truckHeights || []);
    state.constructions = orderSpecValues("constructions", snapshot.constructions || []);
    state.abecs = orderSpecValues("abecs", snapshot.abecs || []);
    state.shoeSizes = orderSpecValues("shoeSizes", snapshot.shoeSizes || []);
    if (partChanged) syncTypeSections(true);
    const watching = document.getElementById("watchingToggle");
    if (watching) watching.setAttribute("aria-pressed", state.watching ? "true" : "false");
    const grouped = document.getElementById("groupToggle");
    if (grouped) grouped.setAttribute("aria-pressed", state.grouped ? "true" : "false");
    setPressed("#storeFilters [data-store]", "data-store", state.store);
    setPressed("#partFilters [data-part]", "data-part", state.part);
    paintWidthChips();
}

const SEARCH_HISTORY_MS = 400;
let lastHistoryQuery = null;
let ignoreHistory = false;
let searchHistoryTimer = 0;

function onlySearchChanged(previous, next) {
    const before = new URLSearchParams(previous || "");
    const after = new URLSearchParams(next || "");
    const keys = {};
    before.forEach((value, key) => { keys[key] = true; });
    after.forEach((value, key) => { keys[key] = true; });
    let searchDiffered = false;
    const names = Object.keys(keys);
    for (let i = 0; i < names.length; i++) {
        const key = names[i];
        if ((before.get(key) || "") === (after.get(key) || "")) continue;
        if (key !== "q") return false;
        searchDiffered = true;
    }
    return searchDiffered;
}

function historyAction(previous, next) {
    if (previous == null) return "replace";
    if (previous === next) return "none";
    if (onlySearchChanged(previous, next)) return "search";
    return "push";
}

function historyUrl(query) {
    return query ? location.pathname + "?" + query : location.pathname;
}

function commitHistory(query, mode) {
    const target = historyUrl(query);
    const current = location.pathname + location.search;
    if (current !== target) {
        const data = { view: query };
        if (mode === "push") history.pushState(data, "", target);
        else history.replaceState(data, "", target);
    }
    lastHistoryQuery = query;
}

function syncUrl() {
    try {
        const query = encodeState(captureState());
        if (ignoreHistory) {
            lastHistoryQuery = query;
            return;
        }
        const action = historyAction(lastHistoryQuery, query);
        if (action === "none") return;
        if (action === "search") {
            clearTimeout(searchHistoryTimer);
            searchHistoryTimer = setTimeout(() => {
                const latest = encodeState(captureState());
                const follow = historyAction(lastHistoryQuery, latest);
                if (follow === "none") return;
                commitHistory(latest, follow === "replace" ? "replace" : "push");
            }, SEARCH_HISTORY_MS);
            return;
        }
        clearTimeout(searchHistoryTimer);
        commitHistory(query, action === "replace" ? "replace" : "push");
    } catch (err) {
        /* a bad URL must not break filtering */
    }
}

function restoreFromUrl() {
    clearTimeout(searchHistoryTimer);
    ignoreHistory = true;
    try {
        applySnapshot(decodeQuery(location.search));
        scrollResultsToTop();
    } finally {
        ignoreHistory = false;
        lastHistoryQuery = encodeState(captureState());
    }
}

function applySnapshot(snapshot) {
    writeControls(snapshot);
    applySortChoice();
    applyFilters();
}

function loadFromUrl() {
    const snapshot = decodeQuery(location.search);
    const empty = !location.search || location.search === "?";
    if (empty) return;
    applySnapshot(snapshot, false);
}

function customViews() {
    const stored = readJson(VIEWS_KEY, []);
    return Array.isArray(stored) ? stored.filter(view => view && view.name && view.query) : [];
}

function currentQuery() {
    return encodeState(captureState());
}

function paintViews() {
    const row = document.getElementById("viewRow");
    if (!row) return;
    const current = currentQuery();
    const builtins = (catalog().views || []).map(view => Object.assign({ builtin: true }, view));
    const views = builtins.concat(customViews().map(view => Object.assign({ builtin: false }, view)));
    row.innerHTML = "";
    views.forEach(view => {
        const tab = document.createElement("span");
        const viewQuery = encodeState(decodeQuery(view.query));
        tab.className = "view-tab" + (viewQuery === current ? " on" : "");
        tab.dataset.view = view.id || "";
        if (renamingId && renamingId === view.id) {
            const input = document.createElement("input");
            input.type = "text";
            input.value = view.name;
            input.className = "view-rename-input";
            input.setAttribute("aria-label", "Rename view");
            input.addEventListener("keydown", event => {
                if (event.key === "Enter") commitRename(view.id, input.value);
                if (event.key === "Escape") {
                    renamingId = "";
                    paintViews();
                }
            });
            input.addEventListener("blur", () => commitRename(view.id, input.value));
            tab.appendChild(input);
            row.appendChild(tab);
            input.focus();
            return;
        }
        const apply = document.createElement("button");
        apply.type = "button";
        apply.className = "view-apply";
        apply.textContent = view.name;
        apply.addEventListener("click", () => applySnapshot(decodeQuery(view.query)));
        tab.appendChild(apply);
        if (!view.builtin) {
            const rename = document.createElement("button");
            rename.type = "button";
            rename.className = "view-icon";
            rename.textContent = "✎";
            rename.setAttribute("aria-label", "Rename " + view.name);
            rename.addEventListener("click", () => {
                renamingId = view.id;
                paintViews();
            });
            const remove = document.createElement("button");
            remove.type = "button";
            remove.className = "view-icon";
            remove.textContent = "×";
            remove.setAttribute("aria-label", "Delete " + view.name);
            remove.addEventListener("click", () => deleteView(view.id));
            tab.appendChild(rename);
            tab.appendChild(remove);
        }
        row.appendChild(tab);
    });
}

function commitRename(id, name) {
    const text = String(name || "").trim();
    renamingId = "";
    if (!text) {
        paintViews();
        return;
    }
    const views = customViews().map(view => view.id === id ? Object.assign({}, view, { name: text }) : view);
    writeJson(VIEWS_KEY, views);
    paintViews();
}

function deleteView(id) {
    writeJson(VIEWS_KEY, customViews().filter(view => view.id !== id));
    paintViews();
}

function saveCurrentView(name) {
    const text = String(name || "").trim();
    if (!text) return;
    const views = customViews();
    views.push({
        id: "view-" + Date.now().toString(36),
        name: text,
        query: currentQuery()
    });
    writeJson(VIEWS_KEY, views);
    paintViews();
}

function updateMoreCount() {
    let count = 0;
    ["priceMin", "priceMax", "discountMin", "discountMax", "scoreMin", "scoreMax"].forEach(id => {
        if (numOrNull(id) != null) count += 1;
    });
    const length = document.getElementById("lengthSelect");
    const wheel = document.getElementById("wheelbaseSelect");
    if (length && length.value && length.value !== "all") count += 1;
    if (wheel && wheel.value && wheel.value !== "all") count += 1;
    count += (state.widths || []).length;
    const badge = document.getElementById("moreCount");
    const button = document.getElementById("moreFilters");
    if (badge) {
        badge.hidden = count === 0;
        badge.textContent = count ? "(" + count + ")" : "";
    }
    if (button) button.classList.toggle("has-more", count > 0);
}

function toggleMore() {
    const panel = document.getElementById("morePanel");
    const button = document.getElementById("moreFilters");
    if (!panel) return;
    panel.hidden = !panel.hidden;
    if (button) button.setAttribute("aria-expanded", panel.hidden ? "false" : "true");
    measureBar();
}

function shortDate(iso) {
    const bits = String(iso || "").split("-");
    if (bits.length < 3) return iso;
    const month = MONTHS[Number(bits[1]) - 1] || bits[1];
    return month + " " + Number(bits[2]);
}

function changeChain(series) {
    return (series || []).map(point => shortDate(point[0]) + " $" + Number(point[1]).toFixed(2)).join(" → ");
}

function ensureSparkTip() {
    if (sparkTip) return sparkTip;
    sparkTip = document.getElementById("sparkTip");
    return sparkTip;
}

function pointLabel(point) {
    const iso = String(point[0] || "");
    const year = iso.slice(0, 4);
    const price = Number(point[1]);
    const amount = Number.isFinite(price) ? "$" + price.toFixed(2) : "";
    return shortDate(iso) + (year ? ", " + year : "") + (amount ? " · " + amount : "");
}

function showTip(event, text) {
    const tip = ensureSparkTip();
    if (!tip || !text) return;
    tip.hidden = false;
    tip.textContent = text;
    const x = event && Number.isFinite(event.clientX) ? event.clientX : 24;
    const y = event && Number.isFinite(event.clientY) ? event.clientY : 24;
    const width = Math.min(280, tip.offsetWidth || 160);
    tip.style.left = Math.max(8, Math.min(window.innerWidth - width - 8, x + 12)) + "px";
    tip.style.top = Math.max(8, y + 14) + "px";
}

function showSparkTip(event, point) {
    if (!point) return;
    showTip(event, pointLabel(point));
}

function chartHitLabel(hit) {
    if (!hit) return "";
    const when = pointLabel([hit.date, hit.price]);
    if (hit.kind === "drop") return "Price reduction · " + when;
    if (hit.label) return hit.label + " · " + when;
    return when;
}

function nearestChartHit(hits, x, y) {
    let best = null;
    let bestD = Infinity;
    (hits || []).forEach(hit => {
        const dx = hit.x - x;
        const dy = y == null || hit.y == null ? 0 : hit.y - y;
        // A reduction marker is drawn larger, so a pointer on that circle
        // still wins when another marker sits a few pixels away.
        const bias = hit.kind === "drop" ? 8 : (hit.kind ? 5 : 0);
        const d = Math.hypot(dx, dy) - bias;
        if (d < bestD || (d === bestD && hit.kind && !(best && best.kind))) {
            best = hit;
            bestD = d;
        }
    });
    return best;
}

const FILTER_SECTION_KEY = "salesscraper2.filterSections";

function paintFilterSection(section, open) {
    section.classList.toggle("is-open", open);
    const button = section.querySelector(".section-toggle");
    if (button) button.setAttribute("aria-expanded", open ? "true" : "false");
}

function restoreFilterSections() {
    let saved = {};
    try {
        const raw = JSON.parse(localStorage.getItem(FILTER_SECTION_KEY) || "{}");
        if (raw && typeof raw === "object") saved = raw;
    } catch (err) {
        saved = {};
    }
    document.querySelectorAll(".filter-section").forEach(section => {
        const id = section.getAttribute("data-section") || "";
        const open = Object.prototype.hasOwnProperty.call(saved, id) ? !!saved[id] : section.classList.contains("is-open");
        paintFilterSection(section, open);
    });
}

function rememberFilterSections() {
    const saved = {};
    document.querySelectorAll(".filter-section").forEach(section => {
        const id = section.getAttribute("data-section");
        if (id) saved[id] = section.classList.contains("is-open");
    });
    try {
        localStorage.setItem(FILTER_SECTION_KEY, JSON.stringify(saved));
    } catch (err) {
        /* private mode should not break the page */
    }
}

function hideSparkTip() {
    sparkPinned = false;
    const tip = ensureSparkTip();
    if (tip) tip.hidden = true;
}

function nearestPoint(id, event, svg) {
    let points = svg ? sparkPoints.get(svg) : null;
    if (!points || !points.length) {
        const item = (catalog().items || {})[id];
        const daily = item && Array.isArray(item.daily) && item.daily.length ? item.daily : (item && item.series) || [];
        points = clipDailyPrices(daily, chartWindow);
    }
    if (!points.length) return null;
    const rect = svg.getBoundingClientRect();
    if (!rect.width) return points[points.length - 1];
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    const index = Math.round(ratio * (points.length - 1));
    return points[Math.max(0, Math.min(points.length - 1, index))];
}

function openSparkPanel(id, anchor) {
    const item = (catalog().items || {})[id];
    const panel = document.getElementById("sparkPanel");
    if (!panel || !item) return;
    const title = document.getElementById("sparkPanelTitle");
    const text = document.getElementById("sparkPanelText");
    if (title) title.textContent = item.name || "Price history";
    if (text) {
        const chain = changeChain(item.series || []);
        text.textContent = chain || "No price changes tracked yet.";
    }
    panel.hidden = false;
    const rect = anchor.getBoundingClientRect();
    const width = 300;
    const left = Math.min(window.scrollX + rect.left, window.scrollX + document.documentElement.clientWidth - width - 12);
    panel.style.top = (window.scrollY + rect.bottom + 6) + "px";
    panel.style.left = Math.max(8, left) + "px";
}

function closeSparkPanel() {
    const panel = document.getElementById("sparkPanel");
    if (panel) panel.hidden = true;
}

const LAYOUT_KEY = "salesscraper2.layout";
const STORE_COLOR = {
    Zumiez: "#be185d",
    SkateWarehouse: "#1d4ed8",
    CCS: "#059669",
    Tactics: "#d97706",
    "Skate Deluxe": "#6d28d9",
    "Muir Skate": "#0f766e"
};
let chartWindow = 90;
let chartId = "";

function placeFloat(pop, anchor, avoid) {
    if (!pop || !anchor) return;
    const wasHidden = getComputedStyle(pop).display === "none";
    if (wasHidden) pop.style.display = "block";
    const popRect = pop.getBoundingClientRect();
    const box = anchor.getBoundingClientRect();
    const avoidBox = avoid ? avoid.getBoundingClientRect() : null;
    const margin = 8;
    const width = popRect.width;
    const height = popRect.height;
    let left = Math.min(Math.max(margin, box.left), Math.max(margin, window.innerWidth - margin - width));
    const candidates = [box.top - height - 6];
    if (avoidBox && avoidBox.height) candidates.push(avoidBox.bottom + 6);
    candidates.push(box.bottom + 6);
    let top = candidates[0];
    let placed = false;
    candidates.forEach(candidate => {
        if (placed) return;
        const rect = {
            top: candidate,
            bottom: candidate + height,
            left: left,
            right: left + width,
        };
        const hitsPrice = avoidBox && avoidBox.height &&
            rect.top < avoidBox.bottom && rect.bottom > avoidBox.top &&
            rect.left < avoidBox.right && rect.right > avoidBox.left;
        if (candidate >= margin && rect.bottom <= window.innerHeight - margin && !hitsPrice) {
            top = candidate;
            placed = true;
        }
    });
    if (!placed) top = Math.max(margin, Math.min(top, window.innerHeight - margin - height));
    pop.style.position = "fixed";
    pop.style.top = Math.round(top) + "px";
    pop.style.left = Math.round(left) + "px";
    pop.style.right = "auto";
    pop.style.bottom = "auto";
    if (wasHidden) pop.style.display = "";
}

function readLayout() {
    try {
        return localStorage.getItem(LAYOUT_KEY) === "cards" ? "cards" : "table";
    } catch (err) {
        return "table";
    }
}

function applyLayout(mode) {
    const cards = mode === "cards";
    document.documentElement.classList.toggle("layout-cards", cards);
    const tableBtn = document.getElementById("layoutTable");
    const cardBtn = document.getElementById("layoutCards");
    if (tableBtn) tableBtn.setAttribute("aria-pressed", cards ? "false" : "true");
    if (cardBtn) cardBtn.setAttribute("aria-pressed", cards ? "true" : "false");
    try {
        localStorage.setItem(LAYOUT_KEY, cards ? "cards" : "table");
    } catch (err) {
        /* private mode should not break the page */
    }
}

function paintActiveChips() {
    const host = document.getElementById("activeChips");
    if (!host) return;
    const chips = [];
    function add(label, clear) {
        chips.push({ label: label, clear: clear });
    }
    if (state.store !== "all") add("Store: " + state.store, () => filterByStore("all"));
    if (state.part && state.part !== "Decks") {
        const typeLabel = state.part === "all" ? "Type: All types" : "Type: " + state.part;
        add(typeLabel, () => filterByPart("Decks"));
    }
    if (state.brand !== "all") {
        add(state.brand, () => {
            setSelect("brandSelect", "all");
            state.brand = "all";
            applyFilters();
        });
    }
    const covered = {};
    if (specKeyActive("widths")) {
        document.querySelectorAll("#sizeFilters .width-chip").forEach(node => {
            const ids = widthGroupIds(node);
            if (!ids.length || !ids.every(id => (state.widths || []).indexOf(id) >= 0)) return;
            ids.forEach(id => { covered[id] = true; });
            const labelNode = node.querySelector(".width-label");
            const label = labelNode ? labelNode.textContent : ids.join(", ");
            add(label, () => toggleWidthGroup(node));
        });
        (state.widths || []).forEach(id => {
            if (covered[id]) return;
            const range = widthRanges().find(item => item.id === id);
            add(range ? range.label : id, () => toggleWidthRange(id));
        });
    }
    if (state.priceMin != null) {
        add("Min $" + numText(state.priceMin), () => {
            const node = document.getElementById("priceMin");
            if (node) node.value = "";
            applyFilters();
        });
    }
    if (state.priceMax != null) {
        add("Max $" + numText(state.priceMax), () => {
            const node = document.getElementById("priceMax");
            if (node) node.value = "";
            applyFilters();
        });
    }
    if (state.discountMin != null) {
        add(numText(state.discountMin) + "% off or more", () => {
            const node = document.getElementById("discountMin");
            if (node) node.value = "";
            applyFilters();
        });
    }
    if (state.discountMax != null) {
        add(numText(state.discountMax) + "% off or less", () => {
            const node = document.getElementById("discountMax");
            if (node) node.value = "";
            applyFilters();
        });
    }
    if (state.dropInterval && state.dropInterval !== "all") {
        const labels = { day: "Day", week: "Week", month: "Month", quarter: "3 Months" };
        add("Drop: " + (labels[state.dropInterval] || state.dropInterval), () => setDropInterval("all"));
    }
    (state.kinds || []).forEach(kind => {
        const labels = { new: "New", drop: "Price drop", low: "All-time low", back: "Back in stock", hot: "Hot" };
        add(labels[kind] || kind, () => toggleDealType(kind));
    });
    if (state.scoreMin != null) {
        add("Score " + numText(state.scoreMin) + "+", () => {
            const node = document.getElementById("scoreMin");
            if (node) node.value = "";
            applyFilters();
        });
    }
    if (state.scoreMax != null) {
        add("Score ≤ " + numText(state.scoreMax), () => {
            const node = document.getElementById("scoreMax");
            if (node) node.value = "";
            applyFilters();
        });
    }
    if (specKeyActive("length") && state.length !== "all") {
        add("Length " + state.length, () => {
            setSelect("lengthSelect", "all");
            state.length = "all";
            applyFilters();
        });
    }
    if (specKeyActive("wheelbase") && state.wheelbase !== "all") {
        add("Wheelbase " + state.wheelbase, () => {
            setSelect("wheelbaseSelect", "all");
            state.wheelbase = "all";
            applyFilters();
        });
    }
    const specLabels = {
        diameters: value => "Diameter " + value,
        duros: value => value,
        shapes: value => "Shape: " + value.charAt(0).toUpperCase() + value.slice(1),
        truckSizes: value => "Size " + value,
        truckHeights: value => "Height: " + value.charAt(0).toUpperCase() + value.slice(1),
        constructions: value => "Construction: " + value.charAt(0).toUpperCase() + value.slice(1),
        abecs: value => "ABEC " + value,
        shoeSizes: value => "Size " + value
    };
    SPEC_FACETS.forEach(facet => {
        if (!specKeyActive(facet.stateKey)) return;
        (state[facet.stateKey] || []).forEach(value => {
            add(specLabels[facet.stateKey](value), () => toggleSpec(facet.stateKey, value));
        });
    });
    if (state.highlights) add("Highlights", () => toggleDealType("highlights"));
    if (state.watching) add("Watching", () => toggleWatching());
    if (state.cardNew) add("New deals", () => toggleCard("new"));
    if (state.cardDrop) add("Price drops", () => toggleCard("drop"));
    if (state.cardLow) add("All-time lows", () => toggleCard("lowest"));
    if (state.change === "new") add("New since baseline", () => setChange("all"));
    if (state.change === "drop") add("Price drops since baseline", () => setChange("all"));
    if (state.change === "lowest") add("New lows", () => setChange("all"));
    if (state.change === "removed") add("Deals disappeared", () => setChange("all"));
    host.innerHTML = "";
    const wrap = document.getElementById("activeFilters");
    if (!chips.length) {
        host.hidden = true;
        if (wrap) wrap.hidden = true;
        return;
    }
    host.hidden = false;
    if (wrap) wrap.hidden = false;
    chips.forEach(chip => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "active-chip";
        button.textContent = chip.label + " ×";
        button.setAttribute("aria-label", "Remove " + chip.label);
        button.addEventListener("click", chip.clear);
        host.appendChild(button);
    });
}

function updateFreshness() {
    const header = document.querySelector("header");
    const note = document.getElementById("freshness");
    const node = document.getElementById("lastScan");
    if (!header || !node) return;
    const parsed = parseScan(node.getAttribute("datetime") || "");
    const limit = parseFloat(header.getAttribute("data-stale-hours") || "36");
    const stale = Number.isFinite(parsed) && (Date.now() - parsed) / 3600000 > limit;
    const failed = catalog().failed || [];
    header.classList.toggle("is-stale", stale);
    header.classList.toggle("is-failed", failed.length > 0);
    if (!note) return;
    const parts = [];
    if (failed.length) parts.push("Scan failed for " + failed.join(", "));
    if (stale) parts.push("Last scan is stale (older than " + limit + " hours)");
    else if (!failed.length) parts.push("Scan is current");
    if (parts.length) note.textContent = parts.join(". ");
}

function addDays(iso, delta) {
    const date = new Date(String(iso).slice(0, 10) + "T00:00:00Z");
    if (!Number.isFinite(date.getTime())) return iso;
    date.setUTCDate(date.getUTCDate() + delta);
    return date.toISOString().slice(0, 10);
}

function markerColor(kind) {
    if (kind === "drop") return "#15803d";
    if (kind === "back") return "#7c3aed";
    if (kind === "gone") return "#64748b";
    if (kind === "low") return "#ca8a04";
    return "#334155";
}

function clipDailyPrices(points, days) {
    const end = String((catalog().generated || "")).slice(0, 10);
    const start = end ? addDays(end, -Number(days || 90)) : "";
    return (points || []).filter(point => {
        const day = String(point[0] || "").slice(0, 10);
        if (!day) return false;
        if (start && day < start) return false;
        if (end && day > end) return false;
        return true;
    });
}

function sparkDirection(points) {
    if (!points || points.length < 2) return "flat";
    const last = Number(points[points.length - 1][1]);
    if (!Number.isFinite(last)) return "flat";
    for (let i = points.length - 2; i >= 0; i--) {
        const price = Number(points[i][1]);
        if (Number.isFinite(price) && Math.abs(price - last) > 0.001) return last < price ? "down" : "up";
    }
    return "flat";
}

const SPARK_COLOR = { down: "#15803d", up: "#b91c1c", flat: "#94a3b8" };
const HISTORY_COLOR = "#4f46e5";
const sparkPoints = new WeakMap();

function buildSparkSvg(points, width, height, stroke) {
    width = width || 72;
    height = height || 22;
    stroke = stroke || 1.6;
    const direction = sparkDirection(points);
    const color = SPARK_COLOR[direction] || SPARK_COLOR.flat;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "spark");
    svg.setAttribute("data-direction", direction);
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("width", String(width));
    svg.setAttribute("height", String(height));
    svg.setAttribute("aria-hidden", "true");
    const values = (points || []).map(point => Number(point[1])).filter(value => Number.isFinite(value));
    if (!values.length) {
        sparkPoints.set(svg, points || []);
        return svg;
    }
    const low = Math.min.apply(null, values);
    const high = Math.max.apply(null, values);
    const span = high - low || 1;
    const lastIndex = Math.max(values.length - 1, 1);
    const coords = values.map((value, index) => [
        1 + (index / lastIndex) * (width - 2),
        1 + (height - 4) * (1 - (value - low) / span)
    ]);
    if (coords.length >= 2) {
        const poly = document.createElementNS(svg.namespaceURI, "polyline");
        poly.setAttribute("fill", "none");
        poly.setAttribute("stroke", color);
        poly.setAttribute("stroke-width", String(stroke));
        poly.setAttribute("points", coords.map(pair => pair[0].toFixed(1) + "," + pair[1].toFixed(1)).join(" "));
        svg.appendChild(poly);
    }
    const dot = document.createElementNS(svg.namespaceURI, "circle");
    const endPoint = coords[coords.length - 1];
    dot.setAttribute("cx", endPoint[0].toFixed(1));
    dot.setAttribute("cy", endPoint[1].toFixed(1));
    dot.setAttribute("r", height <= 14 ? "1.5" : (width > 80 ? "2.4" : "2.2"));
    dot.setAttribute("fill", color);
    svg.appendChild(dot);
    sparkPoints.set(svg, points || []);
    return svg;
}

function paintOneSpark(button) {
    const item = (catalog().items || {})[button.dataset.id];
    const daily = item && Array.isArray(item.daily) ? item.daily : [];
    const card = button.classList.contains("spark-card");
    const points = clipDailyPrices(daily, chartWindow);
    const flat = card && sparkDirection(points) === "flat";
    const svg = buildSparkSvg(
        points,
        card ? 156 : 72,
        card ? (flat ? 12 : 30) : 22,
        card ? (flat ? 1.5 : 2) : 1.6
    );
    const existing = button.querySelector("svg");
    if (existing) existing.replaceWith(svg);
    else button.appendChild(svg);
    button.dataset.sparkWindow = String(chartWindow);
}

function paintSparklines() {
    document.querySelectorAll(".spark-hit").forEach(paintOneSpark);
}

let chartObserver = null;
let chartGeneration = 0;

function chartNodeFresh(node) {
    if (!chartGeneration) return true;
    if (node.classList.contains("deal-card")) {
        const button = node.querySelector(".spark-hit");
        const stat = node.querySelector(".avg-price");
        const sparkOk = !button || button.dataset.sparkWindow === String(chartGeneration);
        const statOk = !stat || stat.dataset.statWindow === String(chartGeneration);
        return sparkOk && statOk;
    }
    return node.dataset.sparkWindow === String(chartGeneration);
}

function paintChartTarget(node) {
    if (node.classList.contains("deal-card")) {
        const button = node.querySelector(".spark-hit");
        if (button) {
            paintOneSpark(button);
            button.dataset.sparkWindow = String(chartGeneration);
        }
        paintOneCardStat(node);
        const stat = node.querySelector(".avg-price");
        if (stat) stat.dataset.statWindow = String(chartGeneration);
        return;
    }
    paintOneSpark(node);
    node.dataset.sparkWindow = String(chartGeneration);
}

function refreshCharts() {
    chartGeneration += 1;
    const targets = [];
    document.querySelectorAll("#mainTable .spark-hit").forEach(node => targets.push(node));
    document.querySelectorAll("#cardGrid .deal-card").forEach(node => targets.push(node));
    if (!window.IntersectionObserver) {
        targets.forEach(paintChartTarget);
        return;
    }
    if (!chartObserver) {
        chartObserver = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting || chartNodeFresh(entry.target)) return;
                paintChartTarget(entry.target);
            });
        }, { root: null, rootMargin: "160px" });
    }
    targets.forEach(node => {
        chartObserver.unobserve(node);
        chartObserver.observe(node);
    });
}

function clipSeries(series, days) {
    const end = String((catalog().generated || "")).slice(0, 10);
    const start = end ? addDays(end, -Number(days || 90)) : "";
    const points = (series.points || []).filter(point => !start || point[0] >= start);
    const markers = (series.markers || []).filter(marker => !start || marker.date >= start).map(marker => Object.assign({}, marker));
    if (series.low && series.low.date && (!start || series.low.date >= start)) {
        markers.push({
            date: series.low.date,
            kind: "low",
            label: "All-time low",
            price: series.low.price
        });
    }
    const clipped = {
        store: series.store || "",
        url: series.url || "",
        availability: series.availability || "",
        points: points,
        markers: markers
    };
    if (series.currency) clipped.currency = series.currency;
    if (series.low) clipped.low = series.low;
    return clipped;
}

function drawChart(id) {
    const item = (catalog().items || {})[id];
    const host = document.getElementById("modalChart");
    if (!host || !item) return;
    const series = (item.seriesList || []).map(row => clipSeries(row, chartWindow));
    host.innerHTML = "";
    const width = 640;
    const height = 220;
    const pad = { l: 46, r: 14, t: 16, b: 28 };
    const prices = [];
    series.forEach(row => {
        (row.points || []).forEach(point => prices.push(Number(point[1])));
        (row.markers || []).forEach(marker => {
            if (marker.price != null && Number.isFinite(Number(marker.price))) prices.push(Number(marker.price));
        });
    });
    if (!prices.length) {
        const empty = document.createElement("p");
        empty.className = "chart-empty";
        empty.textContent = "No tracked prices in this window.";
        host.appendChild(empty);
        return;
    }
    const low = Math.min.apply(null, prices);
    const high = Math.max.apply(null, prices);
    const span = high - low || 1;
    const end = String((catalog().generated || "")).slice(0, 10);
    const start = end ? addDays(end, -chartWindow) : end;
    function xOf(iso) {
        const t0 = Date.parse(start + "T00:00:00Z");
        const t1 = Date.parse(end + "T00:00:00Z");
        const t = Date.parse(String(iso).slice(0, 10) + "T00:00:00Z");
        if (!Number.isFinite(t0) || !Number.isFinite(t1) || t1 === t0) return pad.l;
        const ratio = (t - t0) / (t1 - t0);
        return pad.l + Math.min(1, Math.max(0, ratio)) * (width - pad.l - pad.r);
    }
    function yOf(price) {
        return pad.t + (height - pad.t - pad.b) * (1 - (price - low) / span);
    }
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("class", "history-chart");
    svg.setAttribute("role", "img");
    svg.setAttribute("tabindex", "0");
    svg.setAttribute("aria-label", "Price history, " + chartWindow + " days. Hover or tap a point for the date and price.");
    const plate = document.createElementNS(svg.namespaceURI, "rect");
    plate.setAttribute("x", "0");
    plate.setAttribute("y", "0");
    plate.setAttribute("width", String(width));
    plate.setAttribute("height", String(height));
    plate.setAttribute("fill", "transparent");
    svg.appendChild(plate);
    const hits = [];
    [low, high].forEach(price => {
        const label = document.createElementNS(svg.namespaceURI, "text");
        label.setAttribute("x", "4");
        label.setAttribute("y", yOf(price) + 4);
        label.setAttribute("class", "chart-axis");
        label.textContent = "$" + Number(price).toFixed(0);
        svg.appendChild(label);
    });
    series.forEach(row => {
        const color = HISTORY_COLOR;
        const points = row.points || [];
        points.forEach(point => {
            hits.push({ x: xOf(point[0]), y: yOf(Number(point[1])), date: point[0], price: point[1] });
        });
        if (points.length >= 2) {
            const poly = document.createElementNS(svg.namespaceURI, "polyline");
            poly.setAttribute("fill", "none");
            poly.setAttribute("stroke", color);
            poly.setAttribute("stroke-width", "2");
            poly.setAttribute("points", points.map(point => xOf(point[0]).toFixed(1) + "," + yOf(Number(point[1])).toFixed(1)).join(" "));
            svg.appendChild(poly);
        } else if (points.length === 1) {
            const dot = document.createElementNS(svg.namespaceURI, "circle");
            dot.setAttribute("cx", xOf(points[0][0]));
            dot.setAttribute("cy", yOf(Number(points[0][1])));
            dot.setAttribute("r", "3.5");
            dot.setAttribute("fill", color);
            svg.appendChild(dot);
        }
        (row.markers || []).forEach(marker => {
            let price = marker.price;
            if (price == null) {
                const found = points.find(point => point[0] === marker.date);
                price = found ? found[1] : null;
            }
            if (price == null || !Number.isFinite(Number(price))) return;
            const mark = document.createElementNS(svg.namespaceURI, "circle");
            const mx = xOf(marker.date);
            const my = yOf(Number(price));
            mark.setAttribute("cx", mx);
            mark.setAttribute("cy", my);
            mark.setAttribute("r", marker.kind === "drop" ? "6.5" : (marker.kind === "low" ? "5.5" : "4.5"));
            mark.setAttribute("fill", markerColor(marker.kind));
            mark.setAttribute("stroke", marker.kind === "drop" ? "#14532d" : "#ffffff");
            mark.setAttribute("stroke-width", marker.kind === "drop" ? "2" : "1.2");
            if (marker.kind === "drop") mark.setAttribute("class", "marker-drop");
            const title = document.createElementNS(svg.namespaceURI, "title");
            title.textContent = chartHitLabel({ date: marker.date, price: price, kind: marker.kind, label: marker.label });
            mark.appendChild(title);
            hits.push({ x: mx, y: my, date: marker.date, price: price, kind: marker.kind, label: marker.label || "" });
            svg.appendChild(mark);
        });
    });
    function tipAt(event) {
        const rect = svg.getBoundingClientRect();
        if (!rect.width) return;
        const x = (event.clientX - rect.left) * (width / rect.width);
        const y = (event.clientY - rect.top) * (height / rect.height);
        const hit = nearestChartHit(hits, x, y);
        if (!hit) {
            if (!sparkPinned) hideSparkTip();
            return;
        }
        showTip(event, chartHitLabel(hit));
    }
    svg.addEventListener("mousemove", event => {
        sparkPinned = false;
        tipAt(event);
    });
    svg.addEventListener("mouseleave", () => {
        if (!sparkPinned) hideSparkTip();
    });
    svg.addEventListener("click", event => {
        event.stopPropagation();
        sparkPinned = true;
        tipAt(event);
    });
    svg.addEventListener("focus", () => {
        const last = hits.length ? hits[hits.length - 1] : null;
        if (!last) return;
        const rect = svg.getBoundingClientRect();
        showTip({ clientX: rect.left + 24, clientY: rect.top + 24 }, chartHitLabel(last));
    });
    svg.addEventListener("blur", () => {
        if (!sparkPinned) hideSparkTip();
    });
    host.appendChild(svg);
    const legend = document.createElement("p");
    legend.className = "chart-legend";
    legend.textContent = "Green: price reduction. Purple: back in stock. Gray: gone. Gold: all-time low.";
    host.appendChild(legend);
    const stores = document.createElement("p");
    stores.className = "chart-stores";
    stores.textContent = series.map(row => row.store + (row.availability ? " · " + row.availability : "")).join("   ");
    host.appendChild(stores);
}

function setChartWindow(days) {
    const next = Number(days) || 90;
    const changed = next !== chartWindow;
    chartWindow = next;
    document.querySelectorAll("[data-window]").forEach(button => {
        const on = String(button.getAttribute("data-window")) === String(chartWindow);
        button.setAttribute("aria-pressed", on ? "true" : "false");
    });
    if (changed) refreshCharts();
    if (chartId) drawChart(chartId);
}

function openProduct(id) {
    const item = (catalog().items || {})[id];
    const modal = document.getElementById("productModal");
    if (!modal || !item) return;
    chartId = id;
    const title = document.getElementById("modalTitle");
    if (title) title.textContent = item.name || "Price history";
    const meta = document.getElementById("modalMeta");
    if (meta) {
        const bits = [item.store, item.part];
        if (item.size) bits.push(item.size + '"');
        if (item.length) bits.push(item.length + '" long');
        if (item.wheelbase) bits.push(item.wheelbase + '" wheelbase');
        if (item.held) bits.push(item.held);
        if (item.stage) bits.push(item.stage);
        meta.textContent = bits.filter(Boolean).join(" · ");
    }
    const note = document.getElementById("modalNote");
    if (note) note.textContent = item.chartNote || catalog().chartNote || "";
    const list = document.getElementById("modalOffers");
    if (list) {
        list.innerHTML = "";
        (item.offers || []).forEach(offer => {
            const li = document.createElement("li");
            if (offer.cheapest) li.className = "cheapest";
            if (offer.cheapest) {
                const tag = document.createElement("strong");
                tag.textContent = "Cheapest ";
                li.appendChild(tag);
            }
            const symbol = String(offer.currency || "USD").toUpperCase() === "EUR" ? "€" : "$";
            const label = (offer.store || "Store") + " " + symbol + Number(offer.price).toFixed(2) + " · " + (offer.availability || "On sale");
            if (offer.url) {
                const link = document.createElement("a");
                link.href = offer.url;
                link.target = "_blank";
                link.rel = "noopener";
                link.textContent = label;
                li.appendChild(link);
            } else {
                li.appendChild(document.createTextNode(label));
            }
            list.appendChild(li);
        });
    }
    const link = document.getElementById("modalLink");
    if (link) {
        if (item.url) {
            link.hidden = false;
            link.href = item.url;
            link.textContent = "View at " + (item.store || "the store");
        } else {
            link.hidden = true;
        }
    }
    document.querySelectorAll(".deal-card.is-preview").forEach(card => card.classList.remove("is-preview"));
    document.querySelectorAll(".score-cell.pinned").forEach(cell => {
        cell.classList.remove("pinned");
        cell.querySelectorAll(".score-btn, .score-info").forEach(control => {
            control.setAttribute("aria-expanded", "false");
        });
    });
    modal.hidden = false;
    setChartWindow(chartWindow || 90);
}

function closeProduct() {
    const modal = document.getElementById("productModal");
    if (modal) modal.hidden = true;
    chartId = "";
}

let navMode = "deals";

function paintNav() {
    const mode = navMode === "insights" ? "insights" : (state.watching ? "track" : "deals");
    [
        ["navDeals", "deals"],
        ["navTrack", "track"],
        ["navInsights", "insights"]
    ].forEach(pair => {
        const node = document.getElementById(pair[0]);
        if (!node) return;
        const on = mode === pair[1];
        node.classList.toggle("is-active", on);
        node.setAttribute("aria-pressed", on ? "true" : "false");
        if (on) node.setAttribute("aria-current", "page");
        else node.removeAttribute("aria-current");
    });
}

function showDeals() {
    navMode = "deals";
    if (state.watching) toggleWatching();
    else paintNav();
    const section = document.getElementById("dealsSection");
    if (section) section.scrollIntoView({ block: "start" });
}

function showTrack() {
    navMode = "deals";
    if (!state.watching) toggleWatching();
    else paintNav();
    const section = document.getElementById("dealsSection");
    if (section) section.scrollIntoView({ block: "start" });
}

function showInsights() {
    navMode = "insights";
    const panel = document.getElementById("statsPanel");
    const toggle = document.getElementById("statsToggle");
    if (panel && panel.hidden && toggle) toggle.click();
    else if (panel) panel.scrollIntoView({ block: "start" });
    paintNav();
}

function placeCardFloats(card) {
    const price = card.querySelector(".card-prices");
    const hover = card.querySelector(".card-hover");
    const title = card.querySelector(".title-pop");
    const titleAnchor = card.querySelector(".title-slot") || card;
    if (hover) placeFloat(hover, card, price);
    if (title) placeFloat(title, titleAnchor, price);
}

function placeScoreFloat(cell, anchor) {
    const why = cell.querySelector(".why");
    const priceCard = cell.closest(".deal-card");
    const price = priceCard ? priceCard.querySelector(".card-prices") : null;
    if (why) placeFloat(why, anchor || cell, price);
}

function wireDealEvents() {
    document.addEventListener("click", event => {
        const spark = event.target.closest(".spark-hit");
        if (spark) {
            event.preventDefault();
            event.stopPropagation();
            const current = spark.querySelector("svg");
            sparkPinned = true;
            showSparkTip(event, nearestPoint(spark.dataset.id, event, current));
            return;
        }
        const score = event.target.closest(".score-btn, .score-info");
        if (score) {
            event.stopPropagation();
            const cell = score.closest(".score-cell");
            if (!cell) return;
            const pinned = cell.classList.toggle("pinned");
            cell.querySelectorAll(".score-btn, .score-info").forEach(control => {
                control.setAttribute("aria-expanded", pinned ? "true" : "false");
            });
            if (pinned) placeScoreFloat(cell, score);
            return;
        }
        const more = event.target.closest(".card-more");
        if (more) {
            const card = more.closest(".deal-card");
            if (!card) return;
            const on = card.classList.toggle("show-detail");
            more.setAttribute("aria-expanded", on ? "true" : "false");
            return;
        }
        const star = event.target.closest(".star");
        if (star) {
            toggleStar(star);
            return;
        }
        const priceBtn = event.target.closest(".price-btn");
        if (priceBtn) {
            openProduct(priceBtn.dataset.id);
            return;
        }
        const groupChart = event.target.closest(".group-chart");
        if (groupChart) {
            event.stopPropagation();
            openProduct(groupChart.dataset.id);
            return;
        }
        const row = event.target.closest(".deal-row, .deal-card");
        if (!row || event.target.closest("a, button, input, select, label")) return;
        openProduct(row.dataset.id);
    }, true);
    document.addEventListener("keydown", event => {
        if (event.key !== "Enter" && event.key !== " ") return;
        const row = event.target.closest(".deal-row, .deal-card");
        if (!row) return;
        event.preventDefault();
        openProduct(row.dataset.id);
    });
    document.addEventListener("mousemove", event => {
        const spark = event.target.closest(".spark-hit");
        if (!spark) return;
        const current = spark.querySelector("svg");
        if (!current) return;
        sparkPinned = false;
        showSparkTip(event, nearestPoint(spark.dataset.id, event, current));
    });
    document.addEventListener("mouseover", event => {
        const cell = event.target.closest(".score-cell");
        if (cell && !(event.relatedTarget && cell.contains(event.relatedTarget))) {
            const anchor = cell.querySelector(".score-info") || cell.querySelector(".score-btn") || cell;
            placeScoreFloat(cell, anchor);
        }
        const card = event.target.closest(".deal-card");
        if (!card || (event.relatedTarget && card.contains(event.relatedTarget))) return;
        card.classList.add("is-preview");
        placeCardFloats(card);
    });
    document.addEventListener("mouseout", event => {
        const spark = event.target.closest(".spark-hit");
        if (spark && !(event.relatedTarget && spark.contains(event.relatedTarget)) && !sparkPinned) hideSparkTip();
        const card = event.target.closest(".deal-card");
        if (!card || (event.relatedTarget && card.contains(event.relatedTarget))) return;
        card.classList.remove("is-preview");
    });
    document.addEventListener("focusin", event => {
        const spark = event.target.closest(".spark-hit");
        if (spark) {
            const current = spark.querySelector("svg");
            const rect = spark.getBoundingClientRect();
            const point = nearestPoint(spark.dataset.id, { clientX: rect.left, clientY: rect.bottom }, current);
            if (point) showSparkTip({ clientX: rect.left, clientY: rect.bottom }, point);
        }
        const cell = event.target.closest(".score-cell");
        if (cell) {
            const anchor = cell.querySelector(".score-info") || cell.querySelector(".score-btn") || cell;
            placeScoreFloat(cell, anchor);
        }
        const card = event.target.closest(".deal-card");
        if (!card) return;
        card.classList.add("is-preview");
        placeCardFloats(card);
    });
    document.addEventListener("focusout", event => {
        const spark = event.target.closest(".spark-hit");
        if (spark && !(event.relatedTarget && spark.contains(event.relatedTarget)) && !sparkPinned) hideSparkTip();
        const card = event.target.closest(".deal-card");
        if (!card || (event.relatedTarget && card.contains(event.relatedTarget))) return;
        card.classList.remove("is-preview");
    });
}

function init() {
    restoreFilterSections();
    syncTypeSections(false);
    applyLayout(readLayout());
    prepareVisit();
    applyStars();
    updateAgo();
    updateBanners();
    measureBar();
    window.addEventListener("resize", measureBar);
    const bar = document.getElementById("stickyBar");
    if (bar && window.ResizeObserver) new ResizeObserver(measureBar).observe(bar);
    const search = document.getElementById("searchInput");
    if (search) search.addEventListener("input", queueFilters);
    ["priceMin", "priceMax", "discountMin", "discountMax", "scoreMin", "scoreMax"].forEach(id => {
        const node = document.getElementById(id);
        if (node) node.addEventListener("input", queueFilters);
    });
    const baseline = document.getElementById("baselineSelect");
    if (baseline) baseline.addEventListener("change", () => setVisitMode(baseline.value));
    const filtersOpen = document.getElementById("filtersOpen");
    const filtersClose = document.getElementById("filtersClose");
    const filterDrawer = document.getElementById("filterDrawer");
    function setFilters(open) {
        if (!filterDrawer) return;
        filterDrawer.classList.toggle("is-open", open);
        document.body.classList.toggle("filters-open", open);
    }
    if (filtersOpen) filtersOpen.addEventListener("click", () => setFilters(true));
    if (filtersClose) filtersClose.addEventListener("click", () => setFilters(false));
    if (filterDrawer) {
        filterDrawer.addEventListener("click", event => {
            const button = event.target.closest(".section-toggle");
            if (!button || !filterDrawer.contains(button)) return;
            const section = button.closest(".filter-section");
            if (!section) return;
            paintFilterSection(section, !section.classList.contains("is-open"));
            rememberFilterSections();
        });
    }
    const scoreInfo = document.getElementById("scoreInfo");
    if (scoreInfo) scoreInfo.addEventListener("click", event => event.stopPropagation());
    const storeSelect = document.getElementById("storeSelect");
    if (storeSelect) storeSelect.addEventListener("change", () => filterByStore(storeSelect.value));
    const partSelect = document.getElementById("partSelect");
    if (partSelect) partSelect.addEventListener("change", () => filterByPart(partSelect.value));
    const storeFilters = document.getElementById("storeFilters");
    if (storeFilters) {
        storeFilters.addEventListener("click", event => {
            const button = event.target.closest(".quick-chip[data-store]");
            if (!button || !storeFilters.contains(button)) return;
            filterByStore(button.getAttribute("data-store") || "all");
        });
    }
    const partFilters = document.getElementById("partFilters");
    if (partFilters) {
        partFilters.addEventListener("click", event => {
            const button = event.target.closest(".quick-chip[data-part]");
            if (!button || !partFilters.contains(button)) return;
            filterByPart(button.getAttribute("data-part") || "Decks");
        });
    }
    document.querySelectorAll(".more-toggle").forEach(button => {
        button.addEventListener("click", event => {
            event.stopPropagation();
            const list = document.getElementById(button.getAttribute("aria-controls") || "");
            if (!list) return;
            const open = list.hidden;
            document.querySelectorAll(".more-list").forEach(other => { other.hidden = true; });
            document.querySelectorAll(".more-toggle").forEach(other => {
                other.setAttribute("aria-expanded", "false");
            });
            list.hidden = !open;
            button.setAttribute("aria-expanded", open ? "true" : "false");
        });
    });
    document.addEventListener("click", event => {
        if (event.target.closest(".more-menu")) return;
        document.querySelectorAll(".more-list").forEach(list => { list.hidden = true; });
        document.querySelectorAll(".more-toggle").forEach(button => {
            button.setAttribute("aria-expanded", "false");
        });
    });
    const navPills = document.getElementById("navPills");
    if (navPills && window.ResizeObserver) new ResizeObserver(scheduleNavFit).observe(navPills);
    else window.addEventListener("resize", scheduleNavFit);
    const brand = document.getElementById("brandSelect");
    if (brand) brand.addEventListener("change", applyFilters);
    const brandList = document.getElementById("brandList");
    if (brandList) {
        brandList.addEventListener("click", event => {
            const button = event.target.closest(".facet-value");
            if (!button || !brandList.contains(button)) return;
            setSelect("brandSelect", button.getAttribute("data-brand") || "all");
            applyFilters();
        });
    }
    const brandSearch = document.getElementById("brandSearch");
    if (brandSearch) {
        brandSearch.addEventListener("input", () => filterBrandList(brandSearch.value));
    }
    const length = document.getElementById("lengthSelect");
    if (length) length.addEventListener("change", () => {
        if ((state.part || "Decks") === "all" && length.value && length.value !== "all") {
            state.part = "Decks";
            const select = document.getElementById("partSelect");
            if (select) select.value = "Decks";
            setPressed("#partFilters [data-part]", "data-part", "Decks");
            syncTypeSections(true);
        }
        applyFilters();
    });
    const wheelbase = document.getElementById("wheelbaseSelect");
    if (wheelbase) wheelbase.addEventListener("change", () => {
        if ((state.part || "Decks") === "all" && wheelbase.value && wheelbase.value !== "all") {
            state.part = "Decks";
            const select = document.getElementById("partSelect");
            if (select) select.value = "Decks";
            setPressed("#partFilters [data-part]", "data-part", "Decks");
            syncTypeSections(true);
        }
        applyFilters();
    });
    const sort = document.getElementById("sortSelect");
    if (sort) sort.addEventListener("change", applySortChoice);
    const more = document.getElementById("moreFilters");
    if (more) more.addEventListener("click", toggleMore);
    const save = document.getElementById("saveView");
    const bookmark = document.getElementById("bookmarkView");
    const form = document.getElementById("saveViewForm");
    const openSaveForm = () => {
        if (!form) return;
        form.hidden = false;
        const input = document.getElementById("viewNameInput");
        if (input) input.focus();
    };
    if (save) save.addEventListener("click", openSaveForm);
    if (bookmark) bookmark.addEventListener("click", openSaveForm);
    if (form) {
        form.addEventListener("submit", event => {
            event.preventDefault();
            const input = document.getElementById("viewNameInput");
            saveCurrentView(input ? input.value : "");
            if (input) input.value = "";
            form.hidden = true;
        });
    }
    const cancel = document.getElementById("viewCancel");
    if (cancel && form) {
        cancel.addEventListener("click", () => {
            form.hidden = true;
        });
    }
    wireDealEvents();
    document.querySelectorAll("[data-window]").forEach(button => {
        button.addEventListener("click", () => setChartWindow(button.getAttribute("data-window")));
    });
    const modalClose = document.getElementById("modalClose");
    if (modalClose) modalClose.addEventListener("click", closeProduct);
    const modal = document.getElementById("productModal");
    if (modal) {
        modal.addEventListener("click", event => {
            if (event.target === modal) closeProduct();
        });
    }
    const navDeals = document.getElementById("navDeals");
    const navTrack = document.getElementById("navTrack");
    const navInsights = document.getElementById("navInsights");
    if (navDeals) navDeals.addEventListener("click", showDeals);
    if (navTrack) navTrack.addEventListener("click", showTrack);
    if (navInsights) navInsights.addEventListener("click", showInsights);
    const strip = document.getElementById("categoryStrip");
    if (strip) {
        strip.addEventListener("click", event => {
            const button = event.target.closest("[data-part]");
            if (!button) return;
            filterByPart(button.getAttribute("data-part") || "all");
        });
    }
    const intervals = document.getElementById("dropInterval");
    if (intervals) {
        intervals.addEventListener("click", event => {
            const button = event.target.closest("[data-interval]");
            if (!button) return;
            setDropInterval(button.getAttribute("data-interval") || "all");
        });
    }
    const kinds = document.getElementById("dealTypes");
    if (kinds) {
        kinds.addEventListener("click", event => {
            const button = event.target.closest("[data-kind]");
            if (!button) return;
            toggleDealType(button.getAttribute("data-kind") || "");
        });
    }
    const sizeFilters = document.getElementById("sizeFilters");
    if (sizeFilters) {
        sizeFilters.addEventListener("click", event => {
            const button = event.target.closest(".width-chip");
            if (!button || !sizeFilters.contains(button)) return;
            toggleWidthGroup(button);
        });
    }
    document.querySelectorAll(".spec-ranges").forEach(group => {
        group.addEventListener("click", event => {
            const button = event.target.closest(".spec-chip");
            if (!button || !group.contains(button)) return;
            const facet = SPEC_FACETS.find(item => item.section === group.id);
            if (!facet) return;
            toggleSpec(facet.stateKey, button.getAttribute("data-value") || "");
        });
    });
    document.querySelectorAll(".filters-done").forEach(button => {
        if (button.id === "filtersClose") return;
        button.addEventListener("click", () => setFilters(false));
    });
    document.addEventListener("click", event => {
        if (!filterDrawer || !filterDrawer.classList.contains("is-open")) return;
        if (event.target.closest("#filterDrawer, #filtersOpen")) return;
        setFilters(false);
    });
    wireDuals();
    const layoutTable = document.getElementById("layoutTable");
    const layoutCards = document.getElementById("layoutCards");
    if (layoutTable) layoutTable.addEventListener("click", () => applyLayout("table"));
    if (layoutCards) layoutCards.addEventListener("click", () => applyLayout("cards"));
    document.querySelectorAll(".group-summary").forEach(button => {
        button.addEventListener("click", () => {
            const card = button.closest(".group-card");
            const detail = card ? card.querySelector(".group-detail") : null;
            if (!detail) return;
            const willOpen = detail.hidden;
            detail.hidden = !willOpen;
            button.setAttribute("aria-expanded", willOpen ? "true" : "false");
        });
    });
    const close = document.getElementById("drawerClose");
    if (close) close.addEventListener("click", closeDrawer);
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            hideSparkTip();
            closeDrawer();
            closeSparkPanel();
            closeProduct();
            const drawer = document.getElementById("filterDrawer");
            if (drawer) drawer.classList.remove("is-open");
            document.body.classList.remove("filters-open");
        }
    });
    document.addEventListener("click", event => {
        if (sparkPinned && !event.target.closest(".spark-hit")) hideSparkTip();
        const panel = document.getElementById("sparkPanel");
        if (!panel || panel.hidden) return;
        if (event.target.closest("#sparkPanel, .spark-hit")) return;
        closeSparkPanel();
    });
    updateChangeLine();
    paintViews();
    const diagToggle = document.getElementById("diagToggle");
    const diagnostics = document.getElementById("diagnostics");
    if (diagToggle && diagnostics) {
        diagToggle.addEventListener("click", () => {
            const open = diagnostics.hasAttribute("hidden");
            if (open) diagnostics.removeAttribute("hidden");
            else diagnostics.setAttribute("hidden", "");
            diagToggle.setAttribute("aria-expanded", open ? "true" : "false");
            if (open) diagnostics.scrollIntoView({ block: "nearest" });
        });
    }
    const home = document.getElementById("homeReset");
    if (home) home.addEventListener("click", clearFilters);
    window.addEventListener("popstate", restoreFromUrl);
    if (location.search && location.search.length > 1) loadFromUrl();
    else {
        state.change = "all";
        state.cardNew = false;
        state.cardDrop = false;
        state.cardLow = false;
        applyFilters();
    }
}

document.addEventListener("DOMContentLoaded", updateAgo);
document.addEventListener("DOMContentLoaded", init);
