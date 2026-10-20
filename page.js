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

function shoeOfferMap(raw) {
    const map = Object.create(null);
    String(raw || "").split(",").forEach(part => {
        const bits = part.split(":");
        if (bits.length < 2) return;
        const price = parseFloat(bits[1]);
        if (!bits[0] || !Number.isFinite(price)) return;
        map[bits[0]] = price;
    });
    return map;
}

// The selected size's price, when the in-stock variants do not all cost the same.
function selectedShoePrice(row) {
    const selected = state.shoeSizes || [];
    if (!selected.length || (row.dataset.part || "") !== "Sneakers") return null;
    const prices = shoeOfferMap(row.dataset.shoeprices);
    if (!Object.keys(prices).length) return null;
    const compares = shoeOfferMap(row.dataset.shoecompares);
    const have = specTokens(row, "shoesize").filter(token => selected.indexOf(token) >= 0);
    let best = null;
    have.forEach(token => {
        if (!Object.prototype.hasOwnProperty.call(prices, token)) return;
        const price = prices[token];
        if (!best || price < best.price) best = { price: price, compare: compares[token] };
    });
    return best;
}

function rowPrice(row) {
    const offer = selectedShoePrice(row);
    if (offer) return offer.price;
    const raw = row.dataset.price;
    if (raw === undefined || raw === "") return null;
    const price = parseFloat(raw);
    return Number.isFinite(price) ? price : null;
}

function rowDiscount(row) {
    const offer = selectedShoePrice(row);
    if (!offer) {
        if (row.dataset.discount === "") return null;
        const parsed = parseFloat(row.dataset.discount);
        return Number.isFinite(parsed) ? parsed : null;
    }
    const compare = Number.isFinite(offer.compare) ? offer.compare : parseFloat(row.dataset.original);
    if (!Number.isFinite(compare) || compare <= 0) return null;
    return ((compare - offer.price) / compare) * 100;
}

function paintOfferPrices() {
    document.querySelectorAll(".deal-row, .deal-card").forEach(node => {
        const priceNode = node.querySelector(".price-new, .now-price");
        if (!priceNode) return;
        if (!node.dataset.priceSaved) {
            node.dataset.basePrice = node.dataset.price || "";
            node.dataset.baseDiscount = node.dataset.discount || "";
            node.dataset.priceSaved = "1";
        }
        if (!priceNode.dataset.baseText) priceNode.dataset.baseText = priceNode.textContent;
        const offer = selectedShoePrice(node);
        if (!offer) {
            node.dataset.price = node.dataset.basePrice;
            node.dataset.discount = node.dataset.baseDiscount;
            priceNode.textContent = priceNode.dataset.baseText;
        } else {
            node.dataset.price = offer.price.toFixed(2);
            const percent = rowDiscount(node);
            node.dataset.discount = percent == null ? "" : String(Math.round(percent * 10) / 10);
            const base = priceNode.dataset.baseText;
            const symbol = base.indexOf("€") >= 0 ? "€" : "$";
            const formatted = symbol + offer.price.toFixed(2);
            priceNode.textContent = base.trim().indexOf("Now:") === 0 ? "Now: " + formatted : formatted;
        }
        node.querySelectorAll(".price-old").forEach(oldNode => {
            if (!oldNode.dataset.baseText) oldNode.dataset.baseText = oldNode.textContent;
            if (!offer || !Number.isFinite(offer.compare)) {
                oldNode.textContent = oldNode.dataset.baseText;
                return;
            }
            const symbol = (oldNode.dataset.baseText || "").indexOf("€") >= 0 ? "€" : "$";
            oldNode.textContent = symbol + offer.compare.toFixed(2);
        });
        node.querySelectorAll(".discount").forEach(discountNode => {
            if (!discountNode.dataset.baseText) discountNode.dataset.baseText = discountNode.textContent;
            if (!discountNode.dataset.baseClass) {
                discountNode.dataset.baseClass = ["high", "medium", "low", "none"].filter(name => discountNode.classList.contains(name)).join(" ");
            }
            ["high", "medium", "low", "none"].forEach(name => discountNode.classList.remove(name));
            if (!offer) {
                discountNode.textContent = discountNode.dataset.baseText;
                String(discountNode.dataset.baseClass || "").split(/\s+/).filter(Boolean).forEach(name => discountNode.classList.add(name));
                return;
            }
            const percent = rowDiscount(node);
            const klass = percent == null ? "none" : percent >= 40 ? "high" : percent >= 25 ? "medium" : "low";
            discountNode.classList.add(klass);
            discountNode.textContent = percent == null ? "N/A" : Math.round(percent) + "%";
        });
    });
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
    const price = rowPrice(row);
    if (state.priceMin != null && !(price >= state.priceMin)) return false;
    if (state.priceMax != null && !(price <= state.priceMax)) return false;
    const discountMax = Object.prototype.hasOwnProperty.call(over, "discountMax") ? over.discountMax : state.discountMax;
    if (state.discountMin != null || discountMax != null) {
        const discount = rowDiscount(row);
        if (discount == null) return false;
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

const GROUP_PRICE_NOTE = "Listed sale price only. Delivery charges and tax are not included.";
const GROUP_CHEAPEST_LABEL = "Cheapest available · price only";
const GROUP_LOWEST_LABEL = "Lowest listed price · price only";
let groupSelection = new Map();
let groupReturnFocus = null;
let groupNoteSeq = 0;

function offerAvailable(availability) {
    const label = String(availability || "On sale").trim().toLowerCase();
    return label !== "sold out" && label !== "gone" && label !== "no longer listed";
}

function groupMoney(currency, price) {
    const symbol = String(currency || "USD").toUpperCase() === "EUR" ? "€" : "$";
    const amount = Number(price);
    if (!Number.isFinite(amount)) return "";
    return symbol + amount.toFixed(2);
}

// Rank offers that already share a match key. Availability comes from the
// catalog; a sold-out listing is never the featured cheapest.
function rankGroupOffers(offers) {
    const cleaned = [];
    (offers || []).forEach((offer, index) => {
        if (!offer) return;
        const price = Number(offer.price);
        if (!Number.isFinite(price)) return;
        cleaned.push({
            id: String(offer.id || ""),
            store: offer.store || "Store",
            price: price,
            url: offer.url || "",
            name: offer.name || "",
            part: offer.part || "",
            availability: offer.availability || "On sale",
            currency: String(offer.currency || "USD").toUpperCase(),
            storeClass: offer.storeClass || "",
            available: offerAvailable(offer.availability),
            index: index
        });
    });
    cleaned.sort((a, b) => {
        if (a.available !== b.available) return a.available ? -1 : 1;
        if (a.price !== b.price) return a.price - b.price;
        const store = String(a.store).localeCompare(String(b.store));
        if (store) return store;
        return a.index - b.index;
    });
    if (!cleaned.length) {
        return { mode: "empty", offers: [], featured: null, anyAvailable: false, soldOutCheaper: false };
    }
    const available = cleaned.filter(row => row.available);
    const pool = available.length ? available : cleaned;
    const best = pool[0].price;
    cleaned.forEach(row => {
        row.cheapest = Math.abs(row.price - best) < 0.001 && row.available === (available.length > 0);
        row.featured = false;
    });
    const featured = cleaned.find(row => row.cheapest) || cleaned[0];
    featured.featured = true;
    return {
        mode: cleaned.length === 1 ? "single" : "compare",
        offers: cleaned,
        featured: featured,
        anyAvailable: available.length > 0,
        soldOutCheaper: available.length > 0 && cleaned.some(row => !row.available && row.price + 0.001 < featured.price)
    };
}

function groupOfferStep(index, count, key) {
    if (!count) return 0;
    if (key === "ArrowDown" || key === "ArrowRight") return (index + 1) % count;
    if (key === "ArrowUp" || key === "ArrowLeft") return (index - 1 + count) % count;
    if (key === "Home") return 0;
    if (key === "End") return count - 1;
    return index;
}

function groupKicker(ranked) {
    if (!ranked || !ranked.featured) return "";
    if (ranked.mode === "single") return "One store in this view";
    if (ranked.mode !== "compare") return "";
    return ranked.featured.available ? GROUP_CHEAPEST_LABEL : GROUP_LOWEST_LABEL;
}

function groupNote(ranked) {
    if (!ranked || ranked.mode === "empty") return "";
    if (ranked.mode === "single") return "Only one matching store is in this view. " + GROUP_PRICE_NOTE;
    let note = GROUP_PRICE_NOTE;
    if (ranked.soldOutCheaper) note += " A lower listed price is sold out.";
    return note;
}

function groupGapText(offer, featured) {
    if (!offer || !featured || offer.featured) return "";
    if (String(offer.currency || "USD").toUpperCase() !== String(featured.currency || "USD").toUpperCase()) return "";
    const delta = offer.price - featured.price;
    if (Math.abs(delta) < 0.001) return "Same price";
    const symbol = String(featured.currency || "USD").toUpperCase() === "EUR" ? "€" : "$";
    const sign = delta > 0 ? "+" : "−";
    return sign + symbol + Math.abs(delta).toFixed(2);
}

function rowGroupOffer(row) {
    const item = (catalog().items || {})[row.dataset.id] || {};
    const url = row.dataset.url || item.url || "";
    let availability = "On sale";
    let currency = "USD";
    (item.offers || []).forEach(offer => {
        if (!offer || !url || offer.url !== url) return;
        if (offer.availability) availability = offer.availability;
        if (offer.currency) currency = offer.currency;
    });
    const badge = row.querySelector ? row.querySelector(".store-badge") : null;
    const price = rowPrice(row);
    return {
        id: row.dataset.id || "",
        store: row.dataset.store || item.store || "Store",
        price: price,
        url: url,
        name: row.dataset.name || item.name || "",
        part: row.dataset.part || item.part || "",
        availability: availability,
        currency: currency,
        storeClass: badge ? String(badge.className || "") : ""
    };
}

function chosenGroupOffer(key, ranked) {
    const saved = groupSelection.get(key);
    if (saved) {
        const found = ranked.offers.find(offer => offer.id === saved);
        if (found) return found;
    }
    return ranked.featured;
}

function groupOfferButton(card, id) {
    if (!card || !card.querySelectorAll) return null;
    const buttons = card.querySelectorAll(".group-offer");
    for (let i = 0; i < buttons.length; i++) {
        if (buttons[i].dataset && buttons[i].dataset.id === id) return buttons[i];
    }
    return null;
}

function groupOfferLabel(offer, ranked) {
    const bits = [offer.store, groupMoney(offer.currency, offer.price), offer.availability || "On sale"];
    if (offer.featured) {
        const kicker = groupKicker(ranked);
        if (kicker) bits.push(kicker);
    }
    const gap = groupGapText(offer, ranked.featured);
    if (gap) bits.push(gap);
    return bits.filter(Boolean).join(", ");
}

function renderOfferFace(offer, ranked) {
    const face = document.createElement("span");
    face.className = "group-offer-face";
    const kickerText = offer.featured ? groupKicker(ranked) : "";
    if (kickerText) {
        const kicker = document.createElement("span");
        kicker.className = "group-kicker";
        kicker.textContent = kickerText;
        face.appendChild(kicker);
    }
    const line = document.createElement("span");
    line.className = "group-offer-line";
    const store = document.createElement("span");
    store.className = offer.storeClass && offer.storeClass.indexOf("store-badge") >= 0
        ? offer.storeClass
        : ("store-badge" + (offer.storeClass ? " " + offer.storeClass : ""));
    store.textContent = offer.store;
    const amt = document.createElement("span");
    amt.className = "amt";
    amt.textContent = groupMoney(offer.currency, offer.price);
    const stock = document.createElement("span");
    stock.className = "stock " + (offer.available ? "is-in" : "is-out");
    stock.textContent = offer.availability || "On sale";
    line.append(store, amt, stock);
    const gap = groupGapText(offer, ranked.featured);
    if (gap) {
        const gapNode = document.createElement("span");
        gapNode.className = "group-gap";
        gapNode.textContent = gap;
        line.appendChild(gapNode);
    }
    face.appendChild(line);
    return face;
}

function renderGroupOffer(offer, ranked, selected, noteId, panelId, index) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "group-offer" + (offer.featured ? " is-featured" : "");
    button.dataset.id = offer.id;
    button.dataset.url = offer.url;
    button.dataset.store = offer.store;
    button.dataset.name = offer.name;
    button.dataset.price = String(offer.price);
    button.dataset.currency = offer.currency;
    button.dataset.availability = offer.availability;
    button.id = "group-tab-" + index + "-" + String(offer.id).replace(/[^A-Za-z0-9_-]/g, "");
    button.setAttribute("role", "tab");
    button.setAttribute("aria-controls", panelId);
    const on = offer.id === selected.id;
    button.setAttribute("aria-selected", on ? "true" : "false");
    button.tabIndex = on ? 0 : -1;
    button.setAttribute("aria-label", groupOfferLabel(offer, ranked));
    if (offer.featured && noteId) button.setAttribute("aria-describedby", noteId);
    button.appendChild(renderOfferFace(offer, ranked));
    return button;
}

function fillGroupPanel(panel, offer) {
    if (!panel) return;
    panel.replaceChildren();
    if (!offer) return;
    const label = document.createElement("p");
    label.className = "group-panel-label";
    label.textContent = "Product details";
    const row = document.createElement("div");
    row.className = "group-selected";
    const card = cardFor(offer.id);
    const thumb = card && card.querySelector ? card.querySelector("img") : null;
    if (thumb && thumb.cloneNode) {
        const media = document.createElement("span");
        media.className = "group-selected-media";
        const copy = thumb.cloneNode(true);
        if (copy.removeAttribute) copy.removeAttribute("id");
        media.appendChild(copy);
        row.appendChild(media);
    }
    const text = document.createElement("div");
    const name = document.createElement("p");
    name.className = "group-selected-name";
    name.textContent = offer.name || "";
    const meta = document.createElement("p");
    meta.className = "group-selected-meta";
    meta.textContent = [offer.store, groupMoney(offer.currency, offer.price), offer.availability || "On sale"].filter(Boolean).join(" · ");
    text.append(name, meta);
    row.appendChild(text);
    const actions = document.createElement("div");
    actions.className = "group-actions";
    const quick = document.createElement("button");
    quick.type = "button";
    quick.className = "text-btn group-quick";
    quick.dataset.id = offer.id;
    quick.textContent = "Quick view";
    const history = document.createElement("button");
    history.type = "button";
    history.className = "text-btn group-chart";
    history.dataset.id = offer.id;
    history.textContent = "Price history";
    actions.append(quick, history);
    if (offer.url) {
        const link = document.createElement("a");
        link.className = "group-store-link";
        link.href = offer.url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = "View at " + offer.store;
        actions.appendChild(link);
    }
    panel.append(label, row, actions);
}

function offerFromButton(button, card) {
    const title = card && card.querySelector ? card.querySelector(".group-title") : null;
    return {
        id: button.dataset.id || "",
        store: button.dataset.store || "",
        price: Number(button.dataset.price),
        url: button.dataset.url || "",
        name: button.dataset.name || (title ? title.textContent : ""),
        availability: button.dataset.availability || "On sale",
        currency: button.dataset.currency || "USD"
    };
}

function selectGroupOffer(button, focus) {
    if (!button) return;
    const card = button.closest(".group-card");
    const list = button.closest(".group-offers");
    if (!card || !list) return;
    groupSelection.set(card.dataset.key || "", button.dataset.id || "");
    list.querySelectorAll(".group-offer").forEach(tab => {
        const on = tab === button;
        tab.setAttribute("aria-selected", on ? "true" : "false");
        tab.tabIndex = on ? 0 : -1;
    });
    const panel = card.querySelector(".group-panel");
    if (panel) {
        if (button.id) panel.setAttribute("aria-labelledby", button.id);
        fillGroupPanel(panel, offerFromButton(button, card));
    }
    if (focus && button.focus) button.focus();
}

function moveGroupOffer(event) {
    if (!event.target || !event.target.closest || !event.target.closest("#groupBoard")) return;
    if (["ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft", "Home", "End"].indexOf(event.key) < 0) return;
    let button = event.target.closest(".group-offer");
    if (button && String(button.tagName || "").toUpperCase() !== "BUTTON") button = null;
    const card = event.target.closest(".group-card");
    if (!button && card) button = card.querySelector('.group-offer[aria-selected="true"]');
    const list = button ? button.closest(".group-offers") : null;
    if (!button || !list) return;
    const tabs = Array.from(list.querySelectorAll(".group-offer"));
    const index = tabs.indexOf(button);
    if (index < 0) return;
    event.preventDefault();
    const next = tabs[groupOfferStep(index, tabs.length, event.key)];
    if (next) selectGroupOffer(next, true);
}

function renderGroupCard(key, offers) {
    const ranked = rankGroupOffers(offers);
    const card = document.createElement("article");
    card.className = "group-card";
    card.dataset.key = key;
    if (ranked.mode === "empty") {
        card.hidden = true;
        return card;
    }
    groupNoteSeq += 1;
    const noteId = "group-note-" + groupNoteSeq;
    const panelId = "group-panel-" + groupNoteSeq;
    const selected = chosenGroupOffer(key, ranked) || ranked.featured;
    groupSelection.set(key, selected.id);
    const title = document.createElement("h3");
    title.className = "group-title";
    title.textContent = (ranked.featured && ranked.featured.name) || "Matched product";
    const note = document.createElement("p");
    note.className = "group-note";
    note.id = noteId;
    note.textContent = groupNote(ranked);
    card.append(title, note);
    if (ranked.mode === "compare") {
        const list = document.createElement("div");
        list.className = "group-offers";
        list.setAttribute("role", "tablist");
        list.setAttribute("aria-orientation", "vertical");
        list.setAttribute("aria-label", "Equivalent offers for " + title.textContent);
        ranked.offers.forEach((offer, index) => {
            list.appendChild(renderGroupOffer(offer, ranked, selected, noteId, panelId, index));
        });
        card.appendChild(list);
    } else {
        const only = document.createElement("div");
        only.className = "group-offer is-only";
        only.appendChild(renderOfferFace(ranked.featured, ranked));
        card.appendChild(only);
    }
    const panel = document.createElement("div");
    panel.className = "group-panel";
    panel.id = panelId;
    panel.setAttribute("role", "tabpanel");
    panel.tabIndex = 0;
    const selectedButton = groupOfferButton(card, selected.id);
    if (selectedButton && selectedButton.id) panel.setAttribute("aria-labelledby", selectedButton.id);
    else panel.setAttribute("aria-label", "Product details");
    fillGroupPanel(panel, selected);
    card.appendChild(panel);
    return card;
}

function paintGroupBoard(visibleKeys) {
    const board = document.getElementById("groupBoard");
    if (!board) return;
    const active = document.activeElement;
    const focusInBoard = !!(active && board.contains && board.contains(active));
    const activeId = focusInBoard && active.dataset ? active.dataset.id || "" : "";
    const activeCard = focusInBoard && active.closest ? active.closest(".group-card") : null;
    const activeKey = activeCard ? activeCard.dataset.key || "" : "";
    const byKey = new Map();
    dealRows().forEach(row => {
        const key = row.dataset.group || "";
        if (!key || !visibleKeys.has(key) || row.classList.contains("filtered-out")) return;
        if (!byKey.has(key)) byKey.set(key, []);
        byKey.get(key).push(rowGroupOffer(row));
    });
    board.querySelectorAll(".group-card").forEach(card => card.remove());
    let empty = board.querySelector(".group-empty");
    if (!empty) {
        empty = document.createElement("p");
        empty.className = "group-empty lede";
        empty.textContent = "No products are at more than one store under the conservative match. Rows stay separate.";
        board.appendChild(empty);
    }
    empty.hidden = byKey.size !== 0;
    byKey.forEach((offers, key) => {
        const card = renderGroupCard(key, offers);
        if (!card.hidden) board.appendChild(card);
    });
    board.appendChild(empty);
    if (!focusInBoard || !activeKey) return;
    let card = null;
    board.querySelectorAll(".group-card").forEach(node => {
        if (node.dataset.key === activeKey) card = node;
    });
    const button = card ? groupOfferButton(card, activeId) : null;
    if (button && button.focus) button.focus();
}

function restoreGroupFocus() {
    const node = groupReturnFocus;
    groupReturnFocus = null;
    if (node && node.isConnected && node.focus) node.focus({ preventScroll: true });
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
    dealRows().forEach(row => row.classList.remove("grouped-hide"));
    dealRows().forEach(row => {
        const key = row.dataset.group || "";
        if (!key || row.classList.contains("filtered-out")) return;
        const offer = rowGroupOffer(row);
        if (offer.price == null || !Number.isFinite(Number(offer.price))) return;
        visible.add(key);
    });
    dealRows().forEach(row => {
        const key = row.dataset.group || "";
        if (key && visible.has(key) && !row.classList.contains("filtered-out")) row.classList.add("grouped-hide");
    });
    paintGroupBoard(visible);
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
    paintOfferPrices();
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
    fitCardPhotos();
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
        // Phones swipe each chip row (mobile.css), so every chip stays inline.
        if (window.matchMedia(PHONE_QUERY).matches) {
            clusters.forEach(cluster => {
                cluster.list.querySelectorAll(":scope > .quick-chip").forEach(chip => cluster.row.insertBefore(chip, cluster.menu));
                syncNavMore(cluster);
            });
            return;
        }
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
// Keep in step with the media query at the top of mobile.css.
const PHONE_QUERY = "(max-width: 800px), (max-height: 500px) and (pointer: coarse)";
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
    fitCardPhotos();
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
    paintFiltersCount(chips.length);
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

// The phone Filters button shows how many filters are on (mobile.css).
function paintFiltersCount(count) {
    const button = document.getElementById("filtersOpen");
    if (!button) return;
    if (count) {
        button.setAttribute("data-count", String(count));
        button.setAttribute("aria-label", "Filters, " + count + " active");
    } else {
        button.removeAttribute("data-count");
        button.removeAttribute("aria-label");
    }
}

// Phones scroll the whole page through hundreds of cards, so a button
// appears after a few screens to jump back up. Desktop scrolls inside
// .board, so the window never moves and the button stays hidden.
function initToTop() {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "to-top";
    button.textContent = "↑ Top";
    button.setAttribute("aria-label", "Back to top");
    button.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
    document.body.appendChild(button);
    let queued = false;
    window.addEventListener("scroll", () => {
        if (queued) return;
        queued = true;
        requestAnimationFrame(() => {
            queued = false;
            button.classList.toggle("is-shown", window.scrollY > window.innerHeight * 2);
        });
    }, { passive: true });
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

function openProduct(id, fromGroup) {
    if (!fromGroup) groupReturnFocus = null;
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
        const rankedOffers = rankGroupOffers((item.offers || []).map((offer, index) => ({
            id: (offer && offer.url) || String(index),
            store: offer && offer.store,
            price: offer && offer.price,
            url: offer && offer.url,
            availability: (offer && offer.availability) || "On sale",
            currency: (offer && offer.currency) || "USD"
        })));
        const featuredOffer = rankedOffers.mode === "compare" ? rankedOffers.featured : null;
        (item.offers || []).forEach(offer => {
            const li = document.createElement("li");
            const isFeatured = !!(featuredOffer && offer && offer.url && offer.url === featuredOffer.url);
            if (isFeatured) li.className = "cheapest";
            if (isFeatured) {
                const tag = document.createElement("strong");
                tag.textContent = featuredOffer.available ? "Cheapest available · price only " : "Lowest listed price · price only ";
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
        let priceNote = document.getElementById("modalPriceNote");
        if (!priceNote && list.parentNode) {
            priceNote = document.createElement("p");
            priceNote.id = "modalPriceNote";
            priceNote.className = "group-note";
            list.parentNode.insertBefore(priceNote, list);
        }
        if (priceNote) {
            const many = (item.offers || []).filter(offer => offer && offer.url).length > 1;
            priceNote.hidden = !many;
            priceNote.textContent = many ? "Cheapest available is the lowest price still on sale. Delivery charges and tax are not included." : "";
        }
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
    const wasOpen = !!(modal && !modal.hidden);
    if (modal) modal.hidden = true;
    chartId = "";
    if (wasOpen) restoreGroupFocus();
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

const QUICK_OPEN_MS = 300;
const QUICK_CLOSE_MS = 180;
let quickTimer = 0;
let quickCloseTimer = 0;
let quickCard = null;
let quickPinned = false;
let quickForceSheet = false;

function quickIsSheet() {
    if (window.innerWidth <= 800) return true;
    return window.matchMedia("(pointer: coarse)").matches;
}

function isQuickOpen() {
    const panel = document.getElementById("quickView");
    return !!(panel && !panel.hidden);
}

function quickClip(points, days, end) {
    const endDay = String(end || "").slice(0, 10);
    const start = endDay ? addDays(endDay, -Number(days || 90)) : "";
    return (points || []).filter(point => {
        const day = String(point[0] || "").slice(0, 10);
        if (!day) return false;
        if (start && day < start) return false;
        if (endDay && day > endDay) return false;
        const price = Number(point[1]);
        return Number.isFinite(price);
    });
}

function quickMoney(symbol, amount) {
    const value = Number(amount);
    if (!Number.isFinite(value)) return "";
    return (symbol || "$") + value.toFixed(2);
}

function quickShortDate(iso) {
    const parts = String(iso || "").slice(0, 10).split("-");
    if (parts.length < 3) return "";
    const month = MONTHS[Number(parts[1]) - 1];
    const day = Number(parts[2]);
    if (!month || !day) return "";
    return month + " " + day;
}

function quickOwnSeries(item) {
    const list = (item && item.seriesList) || [];
    const url = item && item.url;
    for (let i = 0; i < list.length; i++) {
        if (url && list[i].url === url) return list[i];
    }
    return list[0] || null;
}

function quickSymbol(item) {
    const offers = (item && item.offers) || [];
    for (let i = 0; i < offers.length; i++) {
        if (item.url && offers[i].url === item.url) {
            return String(offers[i].currency || "USD").toUpperCase() === "EUR" ? "€" : "$";
        }
    }
    return "$";
}

function quickPercent(discount) {
    const value = Number(discount);
    if (!Number.isFinite(value) || value <= 0) return "";
    const rounded = Math.round(value * 10) / 10;
    const text = Math.abs(rounded - Math.round(rounded)) < 0.05
        ? String(Math.round(rounded))
        : rounded.toFixed(1);
    return text + "% off";
}

function quickDayLabel(count) {
    const days = Number(count);
    if (!Number.isFinite(days) || days <= 0) return "";
    return days + (days === 1 ? " day" : " days");
}

function quickFacts(dataset, item, generated) {
    dataset = dataset || {};
    item = item || {};
    const symbol = quickSymbol(item);
    const series = quickOwnSeries(item);
    let points = quickClip(item.daily || [], 90, generated);
    if (!points.length && series) points = quickClip(series.points || [], 90, generated);
    const prices = points.map(point => Number(point[1]));
    let average = null;
    if (prices.length) {
        const sum = prices.reduce((total, price) => total + price, 0);
        average = Math.round((sum / prices.length) * 100) / 100;
    }
    const lowInfo = series && series.low;
    let atl = null;
    if (lowInfo && Number.isFinite(Number(lowInfo.price))) {
        atl = { price: Number(lowInfo.price), date: String(lowInfo.date || "").slice(0, 10) };
    }
    const rows = [];
    const list = Number(dataset.original);
    const now = Number(dataset.price);
    if (Number.isFinite(list) && list > 0) rows.push({ label: "List price", value: quickMoney(symbol, list) });
    if (Number.isFinite(list) && Number.isFinite(now) && list - now > 0.009) {
        rows.push({ label: "You save", value: quickMoney(symbol, list - now) });
    }
    const percent = quickPercent(dataset.discount);
    if (percent) rows.push({ label: "Off", value: percent });
    if (atl) {
        const when = quickShortDate(atl.date);
        rows.push({
            label: "All-time low",
            value: quickMoney(symbol, atl.price) + (when ? " on " + when : "")
        });
    }
    if (average != null) rows.push({ label: "90-day average", value: quickMoney(symbol, average) });
    const first = quickShortDate(item.first);
    if (first) rows.push({ label: "First seen", value: first });
    const tracked = quickDayLabel(dataset.days);
    if (tracked) rows.push({ label: "Tracked", value: tracked });
    const atPrice = quickDayLabel(dataset.daysat);
    if (atPrice && String(dataset.daysat) !== String(dataset.days)) {
        rows.push({ label: "At this price", value: atPrice });
    }
    const specs = [];
    function addSpec(label, value, suffix) {
        const text = String(value == null ? "" : value).trim();
        if (!text) return;
        specs.push({ label: label, value: suffix ? text + suffix : text });
    }
    if (String(dataset.shoesize || "").trim()) {
        addSpec("In stock", String(dataset.shoesize).split(",").map(size => size.trim()).filter(Boolean).join(", "));
    }
    addSpec("Width", dataset.size, '"');
    addSpec("Length", dataset.length, '"');
    addSpec("Wheelbase", dataset.wheelbase, '"');
    addSpec("Diameter", dataset.diameter);
    if (String(dataset.duros || "").trim()) {
        addSpec("Durometer", String(dataset.duros).split(",").map(bit => bit.trim()).filter(Boolean).join(", "));
    }
    addSpec("Shape", dataset.shape);
    addSpec("Truck size", dataset.trucksize);
    addSpec("Truck height", dataset.truckheight);
    addSpec("Construction", dataset.construction);
    addSpec("ABEC", dataset.abec);
    const stores = [];
    (item.offers || []).forEach(offer => {
        if (!offer || !offer.url || offer.url === item.url) return;
        const price = quickMoney(String(offer.currency || "USD").toUpperCase() === "EUR" ? "€" : symbol, offer.price);
        let label = offer.store || "Store";
        if (price) label += " " + price;
        if (offer.cheapest) label += " · lowest";
        stores.push({ url: offer.url, label: label });
    });
    const windowEnd = String(generated || "").slice(0, 10);
    const windowStart = windowEnd ? addDays(windowEnd, -90) : "";
    const markers = ((series && series.markers) || []).filter(marker => {
        const day = String((marker && marker.date) || "").slice(0, 10);
        if (!day) return false;
        if (windowStart && day < windowStart) return false;
        if (windowEnd && day > windowEnd) return false;
        return Number.isFinite(Number(marker.price));
    });
    const viewUrl = item.url || "";
    const storeName = item.store || dataset.store || "the store";
    return {
        symbol: symbol,
        points: points,
        average: average,
        atl: atl,
        markers: markers,
        start: points.length ? String(points[0][0]).slice(0, 10) : "",
        end: points.length ? String(points[points.length - 1][0]).slice(0, 10) : "",
        startText: points.length ? quickShortDate(points[0][0]) : "",
        endText: points.length ? quickShortDate(points[points.length - 1][0]) : "",
        firstText: quickShortDate(item.first),
        rows: rows,
        specs: specs,
        stores: stores,
        viewUrl: viewUrl,
        viewLabel: viewUrl ? "View at " + storeName : ""
    };
}

function quickGalleryImages(item, card) {
    const source = card.querySelector(".hero-wrap img, .thumb-wrap img");
    const urls = [item.image, source && source.getAttribute("src"), ...(Array.isArray(item.images) ? item.images : [])];
    return [...new Set(urls.filter(url => typeof url === "string" && /^https?:\/\//i.test(url)))];
}

function appendQuickGallery(product, item, card) {
    const gallery = document.createElement("div");
    gallery.className = "quick-gallery";
    const frame = document.createElement("div");
    frame.className = "quick-image-frame";
    const image = document.createElement("img");
    image.alt = item.name || "Product photo";
    image.decoding = "async";
    const fallback = document.createElement("span");
    fallback.className = "quick-image-missing";
    fallback.textContent = "Photo unavailable";
    fallback.hidden = true;
    frame.append(image, fallback);
    gallery.appendChild(frame);
    const images = quickGalleryImages(item, card);
    let index = 0;
    let counter;
    function show(next) {
        index = (next + images.length) % images.length;
        image.hidden = false;
        fallback.hidden = true;
        image.alt = (item.name || "Product photo") + (images.length > 1 ? " — photo " + (index + 1) + " of " + images.length : "");
        image.src = images[index];
        if (counter) counter.textContent = (index + 1) + " / " + images.length;
    }
    image.addEventListener("error", () => {
        image.hidden = true;
        fallback.hidden = false;
    });
    if (images.length > 1) {
        const controls = document.createElement("div");
        controls.className = "quick-gallery-controls";
        const previous = document.createElement("button");
        previous.type = "button";
        previous.textContent = "‹";
        previous.setAttribute("aria-label", "Previous photo");
        const next = document.createElement("button");
        next.type = "button";
        next.textContent = "›";
        next.setAttribute("aria-label", "Next photo");
        counter = document.createElement("span");
        counter.setAttribute("role", "status");
        counter.setAttribute("aria-live", "polite");
        previous.addEventListener("click", () => show(index - 1));
        next.addEventListener("click", () => show(index + 1));
        controls.append(previous, counter, next);
        gallery.appendChild(controls);
        gallery.tabIndex = 0;
        gallery.setAttribute("role", "region");
        gallery.setAttribute("aria-label", "Product photos");
        gallery.addEventListener("keydown", event => {
            if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
            event.preventDefault();
            show(index + (event.key === "ArrowRight" ? 1 : -1));
        });
        let startX = null;
        let startY = null;
        frame.addEventListener("touchstart", event => {
            startX = event.touches[0].clientX;
            startY = event.touches[0].clientY;
        }, { passive: true });
        frame.addEventListener("touchend", event => {
            if (startX == null || !event.changedTouches.length) return;
            const dx = event.changedTouches[0].clientX - startX;
            const dy = event.changedTouches[0].clientY - startY;
            if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) show(index + (dx < 0 ? 1 : -1));
            startX = startY = null;
        }, { passive: true });
    }
    if (images.length) show(0);
    else { image.hidden = true; fallback.hidden = false; }
    product.appendChild(gallery);
}

function syncQuickStar(card) {
    const button = document.querySelector("#quickView .quick-star");
    const source = card && card.querySelector(".star");
    if (!button || !source) return;
    const on = source.getAttribute("aria-pressed") === "true" || source.classList.contains("on");
    button.classList.toggle("on", on);
    button.setAttribute("aria-pressed", on ? "true" : "false");
    button.setAttribute("aria-label", "Watch this item");
    button.textContent = on ? "★" : "☆";
}

function setQuickExpanded(on) {
    document.querySelectorAll(".card-more[aria-expanded='true']").forEach(button => {
        button.setAttribute("aria-expanded", "false");
    });
    if (!on || !quickCard) return;
    const more = quickCard.querySelector(".card-more");
    if (more) more.setAttribute("aria-expanded", "true");
}

function fillQuickView(card) {
    const panel = document.getElementById("quickView");
    const body = document.getElementById("quickBody");
    if (!panel || !body || !card) return;
    const item = (catalog().items || {})[card.dataset.id] || {};
    const facts = quickFacts(card.dataset, item, catalog().generated || "");
    const dialog = panel.querySelector(".quick-panel");
    body.replaceChildren();
    const heading = document.createElement("h2");
    heading.id = "quickLabel";
    heading.className = "quick-title";
    heading.textContent = item.name || "Deal quick view";
    if (dialog) dialog.setAttribute("aria-labelledby", "quickLabel");
    const head = document.createElement("div");
    head.className = "quick-head";
    const star = document.createElement("button");
    star.type = "button";
    star.className = "star quick-star";
    const close = document.createElement("button");
    close.type = "button";
    close.className = "quick-close";
    close.textContent = "×";
    close.setAttribute("aria-label", "Close quick view");
    close.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();
        closeQuickView();
    });
    head.append(star, close);
    body.appendChild(head);
    const product = document.createElement("div");
    product.className = "quick-product";
    appendQuickGallery(product, item, card);
    const identity = document.createElement("div");
    identity.className = "quick-identity";
    const store = document.createElement("p");
    store.className = "quick-kicker";
    store.textContent = item.store || card.dataset.store || "";
    const price = document.createElement("div");
    price.className = "quick-price";
    const amount = document.createElement("strong");
    amount.textContent = quickMoney(facts.symbol, card.dataset.price);
    price.appendChild(amount);
    const discount = quickPercent(card.dataset.discount);
    if (discount) {
        const badge = document.createElement("span");
        badge.className = "quick-discount";
        badge.textContent = discount;
        price.appendChild(badge);
    }
    identity.append(store, heading, price);
    appendQuickKeyFacts(identity, card.dataset, facts);
    const signal = quickPriceSignal(card.dataset, card);
    if (signal) identity.appendChild(quickSignal(signal));
    if (item.stage) {
        const stage = document.createElement("p");
        stage.className = "quick-stage";
        stage.textContent = item.stage;
        identity.appendChild(stage);
    }
    appendQuickSpecLine(identity, facts.specs);
    const actions = document.createElement("div");
    actions.className = "quick-actions";
    if (facts.viewUrl) {
        const link = document.createElement("a");
        link.className = "quick-view-link";
        link.href = facts.viewUrl;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = facts.viewLabel;
        actions.appendChild(link);
    }
    if (typeof appendQuickAlert === "function") appendQuickAlert(actions, card);
    if (actions.children.length) identity.appendChild(actions);
    product.appendChild(identity);
    body.appendChild(product);
    syncQuickStar(card);
    appendQuickMore(body, card, item, facts);
}

function appendQuickKeyFacts(parent, dataset, facts) {
    dataset = dataset || {};
    facts = facts || {};
    const symbol = facts.symbol || "$";
    const bits = [];
    const list = Number(dataset.original);
    if (Number.isFinite(list) && list > 0) {
        bits.push({ label: "Original", value: quickMoney(symbol, list), original: true });
    }
    if (facts.atl && Number.isFinite(Number(facts.atl.price))) {
        const when = typeof quickShortDate === "function" ? quickShortDate(facts.atl.date) : "";
        bits.push({
            label: "All-time low",
            value: quickMoney(symbol, facts.atl.price) + (when ? " " + when : "")
        });
    }
    if (facts.average != null && Number.isFinite(Number(facts.average))) {
        bits.push({ label: "90-day average", value: quickMoney(symbol, facts.average) });
    }
    if (!bits.length) return;
    const line = document.createElement("p");
    line.className = "quick-keyfacts";
    bits.forEach((bit, index) => {
        if (index) {
            const sep = document.createElement("span");
            sep.className = "quick-key-sep";
            sep.setAttribute("aria-hidden", "true");
            sep.textContent = "·";
            line.appendChild(sep);
        }
        const item = document.createElement("span");
        item.className = bit.original ? "quick-key is-original" : "quick-key";
        const label = document.createElement("span");
        label.className = "quick-key-label";
        label.textContent = bit.label;
        const value = document.createElement("strong");
        value.textContent = bit.value;
        item.append(label, value);
        line.appendChild(item);
    });
    parent.appendChild(line);
}

function appendQuickSpecLine(parent, specs) {
    if (!specs || !specs.length) return;
    const line = document.createElement("p");
    line.className = "quick-spec-line";
    line.textContent = specs.map(row => row.label + " " + row.value).join(" · ");
    parent.appendChild(line);
}

function appendQuickSpecChips(parent, specs) {
    if (!specs || !specs.length) return;
    const details = document.createElement("div");
    details.className = "quick-details";
    const block = document.createElement("div");
    block.className = "quick-specs";
    specs.forEach(row => {
        const line = document.createElement("p");
        const label = document.createElement("span");
        label.textContent = row.label;
        const chips = document.createElement("span");
        chips.className = "quick-chips";
        row.value.split(",").forEach(value => {
            const chip = document.createElement("span");
            chip.className = "quick-spec-chip";
            chip.textContent = value.trim();
            chips.appendChild(chip);
        });
        line.append(label, chips);
        block.appendChild(line);
    });
    details.appendChild(block);
    parent.appendChild(details);
}

function appendQuickHistoryMeta(parent, facts) {
    const rows = ((facts && facts.rows) || []).filter(row => {
        return row.label === "First seen" || row.label === "At this price";
    });
    if (!rows.length) return;
    const line = document.createElement("p");
    line.className = "quick-history-meta";
    rows.forEach((row, index) => {
        if (index) {
            const sep = document.createElement("span");
            sep.className = "quick-key-sep";
            sep.setAttribute("aria-hidden", "true");
            sep.textContent = "·";
            line.appendChild(sep);
        }
        const item = document.createElement("span");
        const label = document.createElement("span");
        label.className = "quick-key-label";
        label.textContent = row.label;
        const value = document.createElement("strong");
        value.textContent = row.value;
        item.append(label, value);
        line.appendChild(item);
    });
    parent.appendChild(line);
}

function appendQuickMore(body, card, item, facts) {
    facts = facts || {};
    const more = document.createElement("details");
    more.className = "quick-more";
    const summary = document.createElement("summary");
    summary.textContent = "More details";
    more.appendChild(summary);
    appendQuickHistoryMeta(more, facts);
    more.appendChild(quickCompareBlock(card.dataset, facts));
    if ((facts.points || []).length >= 2) {
        const chart = document.createElement("div");
        chart.className = "quick-chart";
        more.appendChild(chart);
        drawQuickChart(chart, facts);
    } else if (facts.firstText || facts.startText) {
        const note = document.createElement("p");
        note.className = "quick-tracking";
        note.textContent = "Tracking since " + (facts.firstText || facts.startText);
        more.appendChild(note);
    }
    appendQuickScore(more, card);
    appendQuickSpecChips(more, facts.specs);
    appendQuickOffers(more, item);
    const panel = document.getElementById("quickView");
    more.addEventListener("toggle", () => {
        if (!panel || panel.classList.contains("is-sheet")) return;
        if (typeof placeQuickView === "function") placeQuickView(card);
    });
    body.appendChild(more);
}

function quickNodeText(card, selector) {
    if (!card || !card.querySelector) return "";
    const node = card.querySelector(selector);
    if (!node) return "";
    const wanted = String(selector || "").split(".").filter(Boolean);
    const classes = String(node.className || "").split(/\s+/);
    if (wanted.length && !wanted.every(name => classes.indexOf(name) >= 0)) return "";
    return String(node.textContent || "").trim();
}

function quickPriceSignal(dataset, card) {
    dataset = dataset || {};
    const since = quickNodeText(card, ".price-since");
    const lowText = quickNodeText(card, ".pill-newlow") || quickNodeText(card, ".quiet-low");
    const dropped = dataset.drop === "1" || since.indexOf("Dropped from") === 0;
    const unchanged = since.indexOf("Price unchanged") === 0;
    const atLow = dataset.lowest === "1" || dataset.hitlow === "1" || !!lowText;
    if (dropped) {
        let detail = since || "The sale price fell in the latest scan.";
        if (atLow && lowText && detail.indexOf(lowText) < 0) detail += " · " + lowText;
        else if (atLow && !lowText) detail += " · now the lowest tracked price";
        return { kind: "drop", title: "New price reduction", detail: detail };
    }
    if (unchanged && atLow) {
        let detail = since;
        if (lowText && detail.indexOf(lowText) < 0) detail += " · " + lowText;
        return { kind: "held", title: "Unchanged price, already low", detail: detail };
    }
    if (since) return { kind: "note", title: since, detail: lowText && since.indexOf(lowText) < 0 ? lowText : "" };
    return null;
}

function quickSignal(signal) {
    const note = document.createElement("p");
    note.className = "quick-signal is-" + signal.kind;
    const title = document.createElement("strong");
    title.textContent = signal.title;
    note.appendChild(title);
    if (signal.detail) {
        const detail = document.createElement("span");
        detail.textContent = signal.detail;
        note.appendChild(detail);
    }
    return note;
}

function quickCompare(dataset, facts) {
    dataset = dataset || {};
    facts = facts || {};
    const symbol = facts.symbol || "$";
    const now = Number(dataset.price);
    const list = Number(dataset.original);
    const days = Number(dataset.days);
    let tracked = "—";
    if (Number.isFinite(days) && days > 0) tracked = days + (days === 1 ? " day" : " days");
    else if (dataset.fresh === "1") tracked = "New";
    const average = facts.average == null ? null : Number(facts.average);
    const low = facts.atl ? Number(facts.atl.price) : null;
    return [
        { label: "Now", value: Number.isFinite(now) ? quickMoney(symbol, now) : "—", hint: "Current sale price" },
        {
            label: "Original",
            value: Number.isFinite(list) && list > 0 ? quickMoney(symbol, list) : "—",
            hint: "Original price",
            original: Number.isFinite(list) && list > 0
        },
        {
            label: "Average",
            value: Number.isFinite(average) ? quickMoney(symbol, average) : "—",
            hint: "90-day average sale price"
        },
        {
            label: "Lowest",
            value: Number.isFinite(low) ? quickMoney(symbol, low) : "—",
            hint: "Lowest tracked price"
        },
        { label: "Tracked", value: tracked, hint: "How long this listing has been tracked" }
    ];
}

function quickCompareBlock(dataset, facts) {
    const compare = document.createElement("div");
    compare.className = "quick-compare";
    compare.setAttribute("role", "group");
    compare.setAttribute("aria-label", "Price comparison");
    quickCompare(dataset, facts).forEach(cell => {
        const item = document.createElement("div");
        if (cell.original) item.className = "is-original";
        const label = document.createElement("span");
        label.textContent = cell.label;
        if (cell.hint) label.title = cell.hint;
        const value = document.createElement("strong");
        value.textContent = cell.value;
        item.append(label, value);
        compare.appendChild(item);
    });
    return compare;
}

function quickHitText(hit, symbol) {
    const iso = String((hit && hit.date) || "").slice(0, 10);
    const parts = iso.split("-");
    let when = iso;
    if (typeof MONTHS !== "undefined" && parts.length >= 3) {
        const month = MONTHS[Number(parts[1]) - 1];
        if (month) when = month + " " + Number(parts[2]) + ", " + parts[0];
    }
    const price = Number(hit && hit.price);
    if (Number.isFinite(price)) when += " · " + (symbol || "$") + price.toFixed(2);
    if (hit && hit.kind === "drop") return "Price reduction · " + when;
    if (hit && hit.kind === "low") return "Lowest tracked price · " + when;
    if (hit && hit.label && hit.kind) return hit.label + " · " + when;
    return when;
}

function drawQuickChart(host, facts) {
    const points = (facts && facts.points) || [];
    host.replaceChildren();
    if (points.length < 2) return;
    const prices = points.map(point => Number(point[1])).filter(value => Number.isFinite(value));
    if (prices.length < 2) return;
    const width = 500;
    const height = window.innerWidth > 800 && window.innerHeight <= 850 ? 118 : 144;
    const pad = { l: 58, r: 12, t: 14, b: 24 };
    const low = Math.min.apply(null, prices);
    const high = Math.max.apply(null, prices);
    const span = high - low || 1;
    const symbol = facts.symbol || "$";
    function axisPrice(price) {
        return symbol + Number(price).toFixed(span < 10 ? 2 : 0);
    }
    function xOf(iso) {
        const start = Date.parse(String(facts.start || points[0][0]).slice(0, 10) + "T00:00:00Z");
        const end = Date.parse(String(facts.end || points[points.length - 1][0]).slice(0, 10) + "T00:00:00Z");
        const time = Date.parse(String(iso).slice(0, 10) + "T00:00:00Z");
        const plot = width - pad.l - pad.r;
        if (!Number.isFinite(start) || !Number.isFinite(end) || end === start) return pad.l + plot / 2;
        return pad.l + Math.min(1, Math.max(0, (time - start) / (end - start))) * plot;
    }
    function yOf(price) {
        if (high === low) return pad.t + (height - pad.t - pad.b) / 2;
        return pad.t + (height - pad.t - pad.b) * (1 - (price - low) / span);
    }
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("class", "history-chart");
    svg.setAttribute("role", "img");
    svg.setAttribute("tabindex", "0");
    const avgText = facts.average == null ? "" : " Average " + symbol + Number(facts.average).toFixed(2) + ".";
    svg.setAttribute(
        "aria-label",
        "90-day price history. High " + symbol + high.toFixed(2) + ", low " + symbol + low.toFixed(2) + "." +
        avgText + " Hover or tap for a date and price."
    );
    const color = (typeof SPARK_COLOR !== "undefined" && typeof sparkDirection === "function")
        ? (SPARK_COLOR[sparkDirection(points)] || SPARK_COLOR.flat)
        : "#334155";
    const poly = document.createElementNS(ns, "polyline");
    poly.setAttribute("fill", "none");
    poly.setAttribute("stroke", color);
    poly.setAttribute("stroke-width", "2.4");
    poly.setAttribute("points", points.map(point => xOf(point[0]).toFixed(1) + "," + yOf(Number(point[1])).toFixed(1)).join(" "));
    svg.appendChild(poly);
    if (facts.average != null && high !== low) {
        const avgPrice = Number(facts.average);
        if (avgPrice >= low - 0.001 && avgPrice <= high + 0.001) {
            const y = yOf(avgPrice);
            const avg = document.createElementNS(ns, "line");
            avg.setAttribute("x1", String(pad.l));
            avg.setAttribute("x2", String(width - pad.r));
            avg.setAttribute("y1", y.toFixed(1));
            avg.setAttribute("y2", y.toFixed(1));
            avg.setAttribute("stroke", "#64748b");
            avg.setAttribute("stroke-dasharray", "4 3");
            avg.setAttribute("stroke-width", "1.2");
            svg.appendChild(avg);
        }
    }
    const seen = {};
    [low, high].forEach(price => {
        const key = Number(price).toFixed(2);
        if (seen[key]) return;
        seen[key] = true;
        const label = document.createElementNS(ns, "text");
        label.setAttribute("x", "2");
        label.setAttribute("y", (yOf(price) + 4).toFixed(1));
        label.setAttribute("class", "chart-axis");
        label.textContent = axisPrice(price);
        svg.appendChild(label);
    });
    const startLabel = document.createElementNS(ns, "text");
    startLabel.setAttribute("x", String(pad.l));
    startLabel.setAttribute("y", String(height - 6));
    startLabel.setAttribute("class", "chart-axis");
    startLabel.textContent = facts.startText || "";
    svg.appendChild(startLabel);
    if (facts.endText && facts.endText !== facts.startText) {
        const endLabel = document.createElementNS(ns, "text");
        endLabel.setAttribute("x", String(width - pad.r));
        endLabel.setAttribute("y", String(height - 6));
        endLabel.setAttribute("text-anchor", "end");
        endLabel.setAttribute("class", "chart-axis");
        endLabel.textContent = facts.endText;
        svg.appendChild(endLabel);
    }
    const last = points[points.length - 1];
    const endDot = document.createElementNS(ns, "circle");
    endDot.setAttribute("cx", xOf(last[0]).toFixed(1));
    endDot.setAttribute("cy", yOf(Number(last[1])).toFixed(1));
    endDot.setAttribute("r", "3.6");
    endDot.setAttribute("fill", color);
    endDot.setAttribute("stroke", "#ffffff");
    endDot.setAttribute("stroke-width", "1.2");
    svg.appendChild(endDot);
    const hits = points.map(point => ({
        x: xOf(point[0]),
        y: yOf(Number(point[1])),
        date: point[0],
        price: point[1]
    }));
    const currentHit = hits[hits.length - 1];
    (facts.markers || []).forEach(marker => {
        const price = Number(marker.price);
        if (!Number.isFinite(price)) return;
        const mx = xOf(marker.date);
        const my = yOf(price);
        const mark = document.createElementNS(ns, "circle");
        mark.setAttribute("cx", mx.toFixed(1));
        mark.setAttribute("cy", my.toFixed(1));
        mark.setAttribute("r", marker.kind === "drop" ? "6" : "4.5");
        const fill = typeof markerColor === "function"
            ? markerColor(marker.kind)
            : (marker.kind === "drop" ? "#15803d" : "#334155");
        mark.setAttribute("fill", fill);
        mark.setAttribute("stroke", marker.kind === "drop" ? "#14532d" : "#ffffff");
        mark.setAttribute("stroke-width", marker.kind === "drop" ? "2" : "1.2");
        svg.appendChild(mark);
        hits.push({
            x: mx,
            y: my,
            date: marker.date,
            price: price,
            kind: marker.kind,
            label: marker.label || ""
        });
    });
    if (facts.atl && facts.atl.date) {
        const atlPrice = Number(facts.atl.price);
        const day = String(facts.atl.date).slice(0, 10);
        const inWindow = (!facts.start || day >= facts.start) && (!facts.end || day <= facts.end);
        if (inWindow && Number.isFinite(atlPrice)) {
            const mx = xOf(day);
            const my = yOf(atlPrice);
            const mark = document.createElementNS(ns, "circle");
            mark.setAttribute("cx", mx.toFixed(1));
            mark.setAttribute("cy", my.toFixed(1));
            mark.setAttribute("r", "5");
            mark.setAttribute("fill", "#ca8a04");
            mark.setAttribute("stroke", "#ffffff");
            mark.setAttribute("stroke-width", "1.2");
            svg.appendChild(mark);
            hits.push({ x: mx, y: my, date: day, price: atlPrice, kind: "low", label: "Lowest tracked price" });
        }
    }
    const readout = document.createElement("p");
    readout.className = "quick-readout";
    readout.textContent = currentHit ? quickHitText(currentHit, symbol) : "";
    function pick(x, y) {
        if (typeof nearestChartHit === "function") return nearestChartHit(hits, x, y);
        let best = hits[0];
        let bestD = Infinity;
        hits.forEach(hit => {
            const d = Math.abs(hit.x - x);
            if (d < bestD) {
                best = hit;
                bestD = d;
            }
        });
        return best;
    }
    function showAt(clientX, clientY) {
        const rect = svg.getBoundingClientRect();
        if (!rect.width || !Number.isFinite(clientX)) return;
        const x = (clientX - rect.left) * (width / rect.width);
        const y = rect.height ? (clientY - rect.top) * (height / rect.height) : 0;
        const hit = pick(x, y);
        if (!hit) return;
        readout.textContent = quickHitText(hit, symbol);
        if (typeof showTip === "function") {
            showTip({ clientX: clientX, clientY: clientY }, readout.textContent);
            if (typeof ensureSparkTip === "function") {
                const tip = ensureSparkTip();
                if (tip && tip.style) tip.style.zIndex = "120";
            }
        }
    }
    svg.addEventListener("mousemove", event => {
        if (typeof sparkPinned !== "undefined") sparkPinned = false;
        showAt(event.clientX, event.clientY);
    });
    svg.addEventListener("mouseleave", () => {
        if (typeof sparkPinned !== "undefined" && sparkPinned) return;
        if (typeof hideSparkTip === "function") hideSparkTip();
    });
    function touchAt(event) {
        const touch = (event.touches && event.touches[0]) || (event.changedTouches && event.changedTouches[0]);
        if (!touch) return;
        if (typeof sparkPinned !== "undefined") sparkPinned = true;
        showAt(touch.clientX, touch.clientY);
    }
    svg.addEventListener("touchstart", touchAt, { passive: true });
    svg.addEventListener("touchmove", touchAt, { passive: true });
    svg.addEventListener("click", event => {
        if (event.stopPropagation) event.stopPropagation();
        if (typeof sparkPinned !== "undefined") sparkPinned = true;
        showAt(event.clientX, event.clientY);
    });
    host.appendChild(svg);
    host.appendChild(readout);
    const legend = document.createElement("p");
    legend.className = "chart-legend";
    legend.textContent = "Green: price reduction. Gold: lowest tracked price. Dashed: 90-day average.";
    host.appendChild(legend);
}

function appendQuickScore(parent, card) {
    const score = card.dataset && card.dataset.score;
    let why = null;
    if (card.querySelector) {
        const node = card.querySelector(".card-score .why");
        if (node && String(node.className || "").split(/\s+/).indexOf("why") >= 0) why = node;
    }
    if (!why && (score == null || score === "")) return;
    const block = document.createElement("details");
    block.className = "quick-score" + (card.dataset && card.dataset.hot === "1" ? " is-hot" : "");
    const summary = document.createElement("summary");
    summary.textContent = "Deal score " + (score || "—") + " of 100" + (card.dataset && card.dataset.hot === "1" ? ", hot" : "");
    block.appendChild(summary);
    if (why && why.cloneNode) {
        const copy = why.cloneNode(true);
        if (copy.removeAttribute) {
            copy.removeAttribute("id");
            copy.removeAttribute("role");
        }
        block.appendChild(copy);
    }
    parent.appendChild(block);
}

function appendQuickOffers(parent, item) {
    const rows = [];
    ((item && item.offers) || []).forEach(offer => {
        if (!offer || !offer.url) return;
        const symbol = String(offer.currency || "USD").toUpperCase() === "EUR" ? "€" : "$";
        const price = Number(offer.price);
        rows.push({
            url: offer.url,
            store: offer.store || "Store",
            price: Number.isFinite(price) ? quickMoney(symbol, price) : "",
            availability: offer.availability || "On sale",
            cheapest: !!offer.cheapest
        });
    });
    if (rows.length < 2) return;
    const block = document.createElement("div");
    block.className = "quick-stores";
    const kicker = document.createElement("p");
    kicker.className = "quick-kicker";
    kicker.textContent = "Across stores";
    const list = document.createElement("ul");
    rows.forEach(row => {
        const li = document.createElement("li");
        if (row.cheapest) li.className = "cheapest";
        const link = document.createElement("a");
        link.href = row.url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = row.store + (row.price ? " " + row.price : "");
        const meta = document.createElement("span");
        meta.textContent = row.availability + (row.cheapest ? " · lowest" : "");
        li.append(link, meta);
        list.appendChild(li);
    });
    block.append(kicker, list);
    parent.appendChild(block);
}

function quickTopLimit() {
    const bar = document.getElementById("stickyBar");
    if (!bar) return 4;
    return Math.max(4, bar.getBoundingClientRect().bottom + 4);
}

function placeQuickView(card) {
    const panel = document.getElementById("quickView");
    if (!panel || panel.classList.contains("is-sheet") || !card) return;
    const rect = card.getBoundingClientRect();
    if (rect.width < 40 || rect.height < 40) {
        closeQuickView();
        return;
    }
    const margin = 8;
    const topLimit = quickTopLimit();
    const width = Math.min(720, window.innerWidth - margin * 2);
    panel.style.width = width + "px";
    panel.style.height = "auto";
    const height = panel.getBoundingClientRect().height;
    // Overlap the anchor slightly so there is no dead gap on the pointer path.
    let left = rect.left;
    if (left + width > window.innerWidth - margin) left = rect.right - width;
    left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));
    const top = Math.max(topLimit, Math.min(rect.top, window.innerHeight - height - margin));
    if (height > window.innerHeight - topLimit - margin) {
        // A short viewport needs the accessible, scrollable sheet rather than clipped facts.
        panel.classList.add("is-sheet");
        panel.querySelector(".quick-panel").setAttribute("aria-modal", "true");
        panel.style.left = panel.style.top = panel.style.width = panel.style.height = "";
        document.body.classList.add("quick-sheet");
        return;
    }
    panel.style.left = left + "px";
    panel.style.top = top + "px";
}

function closeQuickView() {
    clearTimeout(quickTimer);
    clearTimeout(quickCloseTimer);
    const panel = document.getElementById("quickView");
    const returnFocus = quickPinned && panel && panel.contains(document.activeElement)
        && quickCard && quickCard.querySelector(".card-more");
    if (panel) {
        panel.hidden = true;
        panel.classList.remove("is-sheet");
        panel.style.left = "";
        panel.style.top = "";
        panel.style.width = "";
        panel.style.height = "";
        const body = document.getElementById("quickBody");
        if (body) body.replaceChildren();
    }
    document.body.classList.remove("quick-sheet");
    hideSparkTip();
    quickPinned = false;
    quickCard = null;
    quickForceSheet = false;
    setQuickExpanded(false);
    const back = groupReturnFocus;
    groupReturnFocus = null;
    if (back && back.isConnected && back.focus) back.focus({ preventScroll: true });
    else if (returnFocus && returnFocus.isConnected) returnFocus.focus({ preventScroll: true });
}

function openQuickView(card, pinned, forceSheet) {
    if (!card) return;
    quickForceSheet = !!forceSheet;
    if (!quickForceSheet) groupReturnFocus = null;
    clearTimeout(quickTimer);
    clearTimeout(quickCloseTimer);
    quickCard = card;
    quickPinned = !!pinned;
    const panel = document.getElementById("quickView");
    if (!panel) return;
    const sheet = quickForceSheet || quickIsSheet();
    panel.classList.toggle("is-sheet", sheet);
    const dialog = panel.querySelector(".quick-panel");
    if (dialog) dialog.setAttribute("aria-modal", sheet ? "true" : "false");
    fillQuickView(card);
    panel.hidden = false;
    document.body.classList.toggle("quick-sheet", sheet);
    if (sheet) {
        panel.style.left = "";
        panel.style.top = "";
        panel.style.width = "";
        panel.style.height = "";
    } else {
        placeQuickView(card);
    }
    setQuickExpanded(true);
    if (pinned) {
        const close = panel.querySelector(".quick-close");
        if (close) close.focus();
    }
}

function onQuickEnter(card) {
    if (!card || quickIsSheet() || quickPinned) return;
    clearTimeout(quickCloseTimer);
    if (quickCard === card && isQuickOpen()) {
        clearTimeout(quickTimer);
        return;
    }
    if (quickCard && quickCard !== card) closeQuickView();
    clearTimeout(quickTimer);
    quickTimer = setTimeout(() => openQuickView(card, false), QUICK_OPEN_MS);
}

function onQuickLeave(card) {
    if (quickPinned) return;
    clearTimeout(quickTimer);
    if (!isQuickOpen() || quickCard !== card) return;
    clearTimeout(quickCloseTimer);
    quickCloseTimer = setTimeout(() => {
        if (!quickPinned) closeQuickView();
    }, QUICK_CLOSE_MS);
}

function wireQuickView() {
    const panel = document.getElementById("quickView");
    if (!panel) return;
    panel.addEventListener("mouseenter", () => {
        if (!quickPinned) clearTimeout(quickCloseTimer);
    });
    panel.addEventListener("mouseleave", event => {
        if (quickPinned) return;
        const next = event.relatedTarget;
        if (next && quickCard && quickCard.contains(next)) return;
        onQuickLeave(quickCard);
    });
    panel.addEventListener("click", event => {
        if (!panel.classList.contains("is-sheet")) return;
        if (event.target.closest(".quick-panel")) return;
        closeQuickView();
    });
    document.addEventListener("scroll", event => {
        if (!quickCard || !isQuickOpen()) return;
        if (panel.classList.contains("is-sheet")) return;
        const target = event.target;
        if (target && target.closest && target.closest("#quickView")) return;
        if (!quickCard.isConnected) {
            closeQuickView();
            return;
        }
        placeQuickView(quickCard);
    }, true);
    window.addEventListener("resize", () => {
        if (!quickCard || !isQuickOpen()) return;
        const sheet = quickForceSheet || quickIsSheet();
        if (panel.classList.contains("is-sheet") !== sheet) {
            openQuickView(quickCard, quickPinned, quickForceSheet);
            return;
        }
        if (!sheet) placeQuickView(quickCard);
    });
    document.addEventListener("click", event => {
        if (!isQuickOpen()) return;
        if (event.target.closest("#quickView, .card-more, .group-quick, #alertsRoot, #navAlerts")) return;
        closeQuickView();
    });
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
            event.preventDefault();
            event.stopPropagation();
            const card = more.closest(".deal-card");
            if (!card) return;
            if (isQuickOpen() && quickCard === card) closeQuickView();
            else openQuickView(card, true);
            return;
        }
        const star = event.target.closest(".star");
        if (star) {
            if (star.closest("#quickView")) {
                event.preventDefault();
                event.stopPropagation();
                if (quickCard) {
                    const cardStar = quickCard.querySelector(".star");
                    if (cardStar) toggleStar(cardStar);
                    syncQuickStar(quickCard);
                }
                return;
            }
            toggleStar(star);
            return;
        }
        const priceBtn = event.target.closest(".price-btn");
        if (priceBtn) {
            openProduct(priceBtn.dataset.id);
            return;
        }
        const groupQuick = event.target.closest(".group-quick");
        if (groupQuick) {
            event.preventDefault();
            event.stopPropagation();
            const card = cardFor(groupQuick.dataset.id);
            if (!card) return;
            groupReturnFocus = groupQuick;
            if (isQuickOpen() && quickCard === card) closeQuickView();
            else openQuickView(card, true, true);
            return;
        }
        const groupChart = event.target.closest(".group-chart");
        if (groupChart) {
            event.stopPropagation();
            groupReturnFocus = groupChart;
            openProduct(groupChart.dataset.id, true);
            return;
        }
        const groupOffer = event.target.closest(".group-offer");
        if (groupOffer && String(groupOffer.tagName || "").toUpperCase() === "BUTTON") {
            selectGroupOffer(groupOffer, false);
            return;
        }
        const row = event.target.closest(".deal-row, .deal-card");
        if (!row || event.target.closest("a, button, input, select, label")) return;
        openProduct(row.dataset.id);
    }, true);
    document.addEventListener("keydown", event => {
        if (event.target && event.target.closest && event.target.closest("#groupBoard")) {
            moveGroupOffer(event);
        }
        if (event.key !== "Enter" && event.key !== " ") return;
        const row = event.target.closest(".deal-row, .deal-card");
        if (!row || event.target.closest("a, button, input, select, label")) return;
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
        if (event.relatedTarget && event.relatedTarget.closest && event.relatedTarget.closest("#quickView")) return;
        onQuickEnter(card);
    });
    document.addEventListener("mouseout", event => {
        const spark = event.target.closest(".spark-hit");
        if (spark && !(event.relatedTarget && spark.contains(event.relatedTarget)) && !sparkPinned) hideSparkTip();
        const card = event.target.closest(".deal-card");
        if (!card || (event.relatedTarget && card.contains(event.relatedTarget))) return;
        const next = event.relatedTarget;
        if (next && next.closest && next.closest("#quickView")) return;
        onQuickLeave(card);
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
    });
    document.addEventListener("focusout", event => {
        const spark = event.target.closest(".spark-hit");
        if (spark && !(event.relatedTarget && spark.contains(event.relatedTarget)) && !sparkPinned) hideSparkTip();
    });
    wireQuickView();
}

function backdropPixel(r, g, b, a) {
    if (a < 16) return true;
    const max = r > g ? (r > b ? r : b) : (g > b ? g : b);
    const min = r < g ? (r < b ? r : b) : (g < b ? g : b);
    return r >= 236 && g >= 236 && b >= 236 && (max - min) < 22;
}

function contentBox(pixels, sampleWidth, sampleHeight, imageWidth, imageHeight) {
    const width = sampleWidth | 0;
    const height = sampleHeight | 0;
    const imageW = Number(imageWidth) || width;
    const imageH = Number(imageHeight) || height;
    const full = { x: 0, y: 0, w: imageW, h: imageH };
    if (!pixels || width < 1 || height < 1 || !imageW || !imageH) return full;
    let minX = width;
    let minY = height;
    let maxX = -1;
    let maxY = -1;
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const i = (y * width + x) * 4;
            if (backdropPixel(pixels[i], pixels[i + 1], pixels[i + 2], pixels[i + 3])) continue;
            if (x < minX) minX = x;
            if (y < minY) minY = y;
            if (x > maxX) maxX = x;
            if (y > maxY) maxY = y;
        }
    }
    if (maxX < 0) return full;
    const x = minX / width * imageW;
    const y = minY / height * imageH;
    const w = (maxX - minX + 1) / width * imageW;
    const h = (maxY - minY + 1) / height * imageH;
    if (w * h < imageW * imageH * 0.08) return full;
    if (w > imageW * 0.92 && h > imageH * 0.92) return full;
    return { x: x, y: y, w: w, h: h };
}

function paddedBox(box, imageWidth, imageHeight) {
    const imageW = Number(imageWidth) || 0;
    const imageH = Number(imageHeight) || 0;
    const full = { x: 0, y: 0, w: imageW, h: imageH, iw: imageW, ih: imageH };
    if (!box || !imageW || !imageH) return full;
    const roomX = Math.max(0, imageW - box.x - box.w);
    const roomY = Math.max(0, imageH - box.y - box.h);
    const padX = Math.min(box.x, roomX, Math.max(1, box.w * 0.025));
    const padY = Math.min(box.y, roomY, Math.max(1, box.h * 0.025));
    const x = Math.max(0, box.x - padX);
    const y = Math.max(0, box.y - padY);
    return {
        x: x,
        y: y,
        w: Math.min(imageW - x, box.w + padX * 2),
        h: Math.min(imageH - y, box.h + padY * 2),
        iw: imageW,
        ih: imageH
    };
}

function heroFitSize(ar, slotWidth, slotHeight) {
    if (!(ar > 0) || slotWidth < 8 || slotHeight < 8) return null;
    const slotAR = slotWidth / slotHeight;
    if (ar >= slotAR) return { width: slotWidth, height: slotWidth / ar };
    return { width: slotHeight * ar, height: slotHeight };
}

function measureContent(img) {
    const iw = img.naturalWidth;
    const ih = img.naturalHeight;
    const full = { x: 0, y: 0, w: iw, h: ih, iw: iw, ih: ih };
    if (!iw || !ih || typeof document === "undefined") return full;
    const sampleWidth = 72;
    const sampleHeight = Math.max(1, Math.round(ih * sampleWidth / iw));
    const canvas = document.createElement("canvas");
    canvas.width = sampleWidth;
    canvas.height = sampleHeight;
    const ctx = canvas.getContext && canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return full;
    let pixels;
    try {
        ctx.drawImage(img, 0, 0, sampleWidth, sampleHeight);
        pixels = ctx.getImageData(0, 0, sampleWidth, sampleHeight).data;
    } catch (err) {
        return full;
    }
    const box = contentBox(pixels, sampleWidth, sampleHeight, iw, ih);
    return paddedBox(box, iw, ih);
}

function layoutHeroWrap(wrap, ar) {
    const media = wrap.parentElement;
    const slot = media && media.getBoundingClientRect ? media.getBoundingClientRect() : null;
    if (!slot) return false;
    const size = heroFitSize(ar, slot.width, slot.height);
    if (!size) return false;
    wrap.style.width = Math.max(1, size.width) + "px";
    wrap.style.height = Math.max(1, size.height) + "px";
    return true;
}

function relayoutHeroes() {
    if (typeof document === "undefined" || !document.querySelectorAll) return;
    document.querySelectorAll("#cardGrid .hero-wrap.is-fit").forEach(wrap => {
        const ar = Number(wrap.dataset.ar);
        if (ar > 0) layoutHeroWrap(wrap, ar);
    });
}

function applyHero(img, box) {
    const wrap = img.closest ? img.closest(".hero-wrap") : null;
    if (!wrap || !box) return;
    const iw = box.iw || img.naturalWidth;
    const ih = box.ih || img.naturalHeight;
    const w = box.w;
    const h = box.h;
    if (!iw || !ih || !w || !h) return;
    const ar = w / h;
    wrap.dataset.ar = String(ar);
    wrap.classList.add("is-fit");
    wrap.classList.remove("is-missing");
    img.hidden = false;
    img.style.position = "absolute";
    img.style.left = (-box.x / w * 100) + "%";
    img.style.top = (-box.y / h * 100) + "%";
    img.style.width = (iw / w * 100) + "%";
    img.style.height = (ih / h * 100) + "%";
    img.style.maxWidth = "none";
    img.style.maxHeight = "none";
    img.style.objectFit = "fill";
    img.style.margin = "0";
    const ph = img.nextElementSibling;
    if (ph && ph.classList && ph.classList.contains("ph")) ph.hidden = true;
    layoutHeroWrap(wrap, ar);
}

function markMissing(img) {
    if (!img) return;
    img.dataset.fitState = "missing";
    img.hidden = true;
    const ph = img.nextElementSibling;
    if (ph) {
        ph.hidden = false;
        ph.setAttribute("role", "img");
        ph.setAttribute("aria-label", "No photo");
    }
    const wrap = img.closest ? img.closest(".hero-wrap") : null;
    if (wrap) {
        wrap.classList.add("is-missing");
        wrap.classList.remove("is-fit");
        wrap.style.width = "";
        wrap.style.height = "";
    }
}

function markMissingWrap(card) {
    const wrap = card.querySelector(".media .hero-wrap");
    if (!wrap) return;
    wrap.classList.add("is-missing");
    const ph = wrap.querySelector(".ph");
    if (ph) {
        ph.hidden = false;
        ph.setAttribute("role", "img");
        ph.setAttribute("aria-label", "No photo");
    }
}

function settleCardCopy(card) {
    if (!card || card.dataset.copySettled) return;
    const prices = card.querySelector(".card-prices");
    if (!prices) return;
    card.querySelectorAll(".card-off").forEach(node => {
        if (node.parentElement !== prices) prices.appendChild(node);
    });
    card.dataset.copySettled = "1";
}

function primeHero(img) {
    if (!img || img.dataset.fitState) return;
    const src = img.getAttribute("src");
    if (!src) {
        markMissing(img);
        return;
    }
    img.dataset.fitState = "pending";
    const apply = box => {
        img.dataset.fitState = "done";
        applyHero(img, box);
    };
    const natural = () => {
        const paint = () => apply({ x: 0, y: 0, w: img.naturalWidth, h: img.naturalHeight, iw: img.naturalWidth, ih: img.naturalHeight });
        if (img.naturalWidth) paint();
        else img.addEventListener("load", paint, { once: true });
    };
    const start = () => {
        if (typeof Image !== "function") {
            natural();
            return;
        }
        const probe = new Image();
        probe.crossOrigin = "anonymous";
        probe.onload = () => {
            try {
                apply(measureContent(probe));
            } catch (err) {
                apply({ x: 0, y: 0, w: probe.naturalWidth, h: probe.naturalHeight, iw: probe.naturalWidth, ih: probe.naturalHeight });
            }
        };
        probe.onerror = () => natural();
        probe.src = src;
    };
    if (img.complete && img.naturalWidth) start();
    else if (img.complete) markMissing(img);
    else {
        img.addEventListener("load", start, { once: true });
        img.addEventListener("error", () => markMissing(img), { once: true });
    }
}

function primeCard(card) {
    const img = card.querySelector(".media img.hero");
    if (!img) {
        markMissingWrap(card);
        return;
    }
    primeHero(img);
}

let heroObserver = null;
let heroResize = false;

function fitCardPhotos() {
    if (typeof document === "undefined" || !document.querySelectorAll) return;
    const cards = document.querySelectorAll("#cardGrid .deal-card");
    if (!cards || !cards.forEach) return;
    cards.forEach(card => settleCardCopy(card));
    relayoutHeroes();
    const view = (typeof window !== "undefined" && window.innerHeight) || 800;
    const primeIfShown = card => {
        if (!card || card.dataset.heroFit === "1") return false;
        const rect = card.getBoundingClientRect ? card.getBoundingClientRect() : { width: 1, top: 0, bottom: 1 };
        if (!(rect.width > 0 && rect.bottom > -240 && rect.top < view + 240)) return false;
        card.dataset.heroFit = "1";
        primeCard(card);
        return true;
    };
    if (typeof IntersectionObserver === "function") {
        if (!heroObserver) {
            heroObserver = new IntersectionObserver(entries => {
                entries.forEach(entry => {
                    if (!entry.isIntersecting) return;
                    const card = entry.target;
                    heroObserver.unobserve(card);
                    if (card.dataset.heroFit === "1") return;
                    card.dataset.heroFit = "1";
                    primeCard(card);
                });
            }, { rootMargin: "240px 0px" });
        }
        cards.forEach(card => {
            if (card.dataset.heroFit === "1") return;
            if (primeIfShown(card)) {
                if (heroObserver) heroObserver.unobserve(card);
                return;
            }
            if (card.dataset.heroWatch === "1") return;
            card.dataset.heroWatch = "1";
            heroObserver.observe(card);
        });
    } else {
        cards.forEach(card => {
            if (card.dataset.heroFit === "1") return;
            card.dataset.heroFit = "1";
            primeCard(card);
        });
    }
    if (!heroResize && typeof window !== "undefined" && window.addEventListener) {
        heroResize = true;
        window.addEventListener("resize", relayoutHeroes);
    }
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
    initToTop();
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
            if (typeof isAlertsOpen === "function" && isAlertsOpen()) {
                event.preventDefault();
                closeAlerts();
                return;
            }
            hideSparkTip();
            closeDrawer();
            closeSparkPanel();
            closeProduct();
            closeQuickView();
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
    wireAlerts();
}

document.addEventListener("DOMContentLoaded", updateAgo);
document.addEventListener("DOMContentLoaded", init);

/* ALERTS_UI_START
   Email alerts for the static page. Contract: docs/alerts-api-contract.md.
   Tokens stay in the URL fragment. This file has no API secrets. */

const ALERTS_API_BASE = "";
const ALERTS_CONSENT_VERSION = "2026-10-20";
const ALERTS_ACCEPTED_MESSAGE = "If this address can receive mail, we sent a verification link. Alerts stay off until you confirm.";
const ALERTS_LINK_MESSAGE = "If an account exists for this address, we sent a new manage link.";
const ALERTS_RULE_FIELDS = [
    "rule_id", "brand", "name", "part", "width", "min_width", "max_width", "size",
    "max_price", "alert_on_drop", "alert_on_low", "alert_on_stock", "alert_on_new",
    "back_in_stock_width", "product_url", "note", "paused"
];
const ALERTS_PARTS = ["", "Decks", "Trucks", "Wheels", "Bearings", "Sneakers", "Accessories", "Completes"];

const alertsUi = {
    wired: false,
    open: false,
    config: null,
    client: null,
    view: "signup",
    draft: null,
    editingId: "",
    prefs: null,
    token: "",
    busy: false,
    message: "",
    error: "",
    previewToken: "",
    previewKind: "",
    confirmId: "",
    turnstileToken: "",
    returnFocus: null,
    writingHash: false
};

function alertsResolveConfig(env) {
    env = env || {};
    const cfg = env.config || {};
    const host = String(env.host || "");
    const production = /(^|\.)github\.io$/i.test(host);
    const requested = String(cfg.apiBase || cfg.baseUrl || env.metaContent || env.fallbackBase || "").trim();
    const consentVersion = String(cfg.consentVersion || ALERTS_CONSENT_VERSION);
    const turnstileSiteKey = String(cfg.turnstileSiteKey || "").trim();
    const mock = cfg.mock === true || cfg.mode === "mock";
    if (requested && alertsBaseAllowed(requested, production)) {
        return {
            mode: "live",
            apiBase: alertsNormalizeBase(requested),
            consentVersion: consentVersion,
            turnstileSiteKey: turnstileSiteKey,
            production: production
        };
    }
    if (mock && !production) {
        return {
            mode: "mock",
            apiBase: "",
            consentVersion: consentVersion,
            turnstileSiteKey: "",
            production: false
        };
    }
    return {
        mode: "soon",
        apiBase: "",
        consentVersion: consentVersion,
        turnstileSiteKey: "",
        production: production
    };
}

function alertsBaseAllowed(apiBase, production) {
    let url;
    try {
        url = new URL(apiBase);
    } catch (err) {
        return false;
    }
    if (url.username || url.password || url.search || url.hash) return false;
    if (url.protocol === "https:") return true;
    if (!production && url.protocol === "http:" && (url.hostname === "localhost" || url.hostname === "127.0.0.1")) return true;
    return false;
}

function alertsNormalizeBase(apiBase) {
    const url = new URL(apiBase);
    const path = url.pathname.replace(/\/+$/, "");
    return url.origin + path;
}

function alertsPageConfig() {
    let meta = "";
    if (typeof document !== "undefined" && document.querySelector) {
        const node = document.querySelector('meta[name="skatedeals-alerts-api"]');
        if (node) meta = node.getAttribute("content") || "";
    }
    const cfg = (typeof window !== "undefined" && window.SKATEDEALS_ALERTS) || {};
    const host = (typeof location !== "undefined" && location.hostname) || "";
    return alertsResolveConfig({
        config: cfg,
        host: host,
        metaContent: meta,
        fallbackBase: ALERTS_API_BASE
    });
}

function readAlertsFragment(hash) {
    const text = String(hash || "").trim();
    if (!text || text.charAt(0) === "?") return null;
    const raw = text.replace(/^#/, "");
    if (!raw || raw.indexOf("=") < 0) return null;
    const params = new URLSearchParams(raw);
    const verify = params.get("verify");
    if (verify) return { purpose: "verify", token: verify };
    const manage = params.get("manage");
    if (manage) return { purpose: "manage", token: manage };
    const token = params.get("token");
    if (!token) return null;
    let purpose = "auto";
    if (params.get("purpose") === "manage") purpose = "manage";
    else if (params.get("purpose") === "verify") purpose = "verify";
    return { purpose: purpose, token: token };
}

function manageTokenFromVerify(body) {
    body = body || {};
    if (body.manage_token) return String(body.manage_token);
    const link = String(body.manage_link || body.manage_url || "");
    const hash = link.indexOf("#") >= 0 ? link.slice(link.indexOf("#") + 1) : "";
    if (!hash) return "";
    const parsed = readAlertsFragment(hash);
    return parsed && parsed.purpose !== "verify" ? parsed.token : "";
}

function validEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email || "").trim());
}

function normalizeEmail(email) {
    return String(email || "").trim().toLowerCase();
}

function maskEmail(email) {
    const parts = String(email || "").split("@");
    if (parts.length !== 2 || !parts[0] || !parts[1]) return "hidden";
    return parts[0].slice(0, 1) + "***@" + parts[1];
}

function safeProductUrl(value) {
    const text = String(value || "").trim();
    if (/^https:\/\//i.test(text) && text.length <= 500) return text;
    return "";
}

function cleanRule(rule) {
    const copy = {};
    const source = rule || {};
    ALERTS_RULE_FIELDS.forEach(key => {
        if (source[key] != null && source[key] !== "") copy[key] = source[key];
    });
    ["alert_on_drop", "alert_on_low", "alert_on_stock", "alert_on_new", "paused"].forEach(key => {
        if (copy[key] !== true) delete copy[key];
    });
    if (copy.note != null) copy.note = String(copy.note);
    return copy;
}

function blankAlertDraft() {
    return {
        form: "fields",
        match: "brand",
        rule_id: "",
        brand: "",
        name: "",
        part: "Decks",
        size: "",
        product_url: "",
        max_price: "",
        alert_on_drop: true,
        alert_on_low: false,
        alert_on_stock: false,
        alert_on_new: false,
        note: "",
        paused: false,
        store: ""
    };
}

function alertDraftFromDataset(dataset, card) {
    dataset = dataset || {};
    let item = {};
    if (typeof catalog === "function") {
        const data = catalog() || {};
        item = (data.items || {})[dataset.id] || {};
    }
    const part = dataset.part || item.part || "";
    let size = dataset.size || "";
    if (!size && part === "Sneakers") {
        const shoes = String(dataset.shoesize || dataset.shoeSize || "").split(",").map(bit => bit.trim()).filter(Boolean);
        if (shoes.length === 1) size = shoes[0];
    }
    const price = Number(dataset.price);
    const name = dataset.name || item.name || "";
    const brand = dataset.brand || "";
    return {
        form: "card",
        match: name ? "name" : "brand",
        rule_id: "",
        brand: brand,
        name: name,
        part: part,
        size: size,
        product_url: dataset.url || item.url || "",
        max_price: Number.isFinite(price) && price > 0 ? String(Math.round(price * 100) / 100) : "",
        alert_on_drop: true,
        alert_on_low: false,
        alert_on_stock: false,
        alert_on_new: false,
        note: "",
        paused: false,
        store: dataset.store || item.store || ""
    };
}

function draftFromRule(rule) {
    rule = rule || {};
    const draft = blankAlertDraft();
    draft.form = "fields";
    draft.rule_id = rule.rule_id || "";
    draft.brand = rule.brand || "";
    draft.name = rule.name || "";
    draft.match = rule.name && !rule.brand ? "name" : (rule.brand && !rule.name ? "brand" : (rule.name ? "name" : "brand"));
    draft.part = rule.part || "";
    draft.size = rule.size != null && rule.size !== "" ? String(rule.size) : (rule.width != null ? String(rule.width) : "");
    draft.product_url = rule.product_url || "";
    draft.max_price = rule.max_price != null && rule.max_price !== "" ? String(rule.max_price) : "";
    draft.alert_on_drop = !!rule.alert_on_drop;
    draft.alert_on_low = !!rule.alert_on_low;
    draft.alert_on_stock = !!rule.alert_on_stock;
    draft.alert_on_new = !!rule.alert_on_new;
    draft.note = rule.note || "";
    draft.paused = !!rule.paused || rule.status === "paused";
    return draft;
}

function ruleFromDraft(draft) {
    draft = draft || {};
    const rule = {};
    if (draft.rule_id) rule.rule_id = String(draft.rule_id);
    const brand = String(draft.brand || "").trim();
    const name = String(draft.name || "").trim();
    const match = draft.match === "brand" || (!name && brand) ? "brand" : "name";
    if (match === "brand") {
        if (brand) rule.brand = brand;
    } else {
        if (name) rule.name = name;
        if (brand) rule.brand = brand;
        const url = safeProductUrl(draft.product_url);
        if (url) rule.product_url = url;
    }
    const part = String(draft.part || "").trim();
    if (part) rule.part = part;
    const size = String(draft.size || "").trim().replace(/["”″]/g, "");
    if (size) {
        rule.size = size;
        const width = Number(size);
        if (part === "Decks" && Number.isFinite(width) && width > 0 && width < 20) rule.width = width;
    }
    if (String(draft.max_price == null ? "" : draft.max_price).trim() !== "") {
        const price = Number(draft.max_price);
        if (Number.isFinite(price)) rule.max_price = Math.round(price * 100) / 100;
    }
    if (draft.alert_on_drop) rule.alert_on_drop = true;
    if (draft.alert_on_low) rule.alert_on_low = true;
    if (draft.alert_on_stock) {
        rule.alert_on_stock = true;
        if (rule.width != null) rule.back_in_stock_width = rule.width;
    }
    if (draft.alert_on_new) rule.alert_on_new = true;
    const note = String(draft.note || "").trim();
    if (note) rule.note = note;
    if (draft.paused) rule.paused = true;
    return cleanRule(rule);
}

function validateRules(rules, options) {
    options = options || {};
    if (!Array.isArray(rules)) return "Add at least one alert. Nothing was saved.";
    if (options.requireOne && rules.length < 1) return "Add a product or a brand to watch. Nothing was saved.";
    if (rules.length > 10) return "You can save up to 10 alerts. Nothing was saved.";
    for (let i = 0; i < rules.length; i++) {
        const rule = rules[i] || {};
        if (!rule.brand && !rule.name && !rule.product_url) return "Add a product or a brand. Nothing was saved.";
        if (rule.max_price != null && rule.max_price !== "" && !(Number(rule.max_price) > 0)) {
            return "Target price has to be greater than zero. Nothing was saved.";
        }
        if (rule.note && String(rule.note).length > 80) return "Notes have to be 80 characters or fewer. Nothing was saved.";
        if (rule.brand && String(rule.brand).length > 120) return "Brand is too long. Nothing was saved.";
        if (rule.name && String(rule.name).length > 160) return "Product name is too long. Nothing was saved.";
    }
    return "";
}

function validateSignup(email, consent, rules) {
    if (!validEmail(email)) return "Enter the email address that should get the digest. Nothing was saved.";
    if (consent !== true) return "Check the box to agree to the daily digest. Nothing was saved.";
    return validateRules(rules, { requireOne: true });
}

function ruleBadge(subscriberStatus, rule) {
    rule = rule || {};
    const paused = !!rule.paused || rule.status === "paused";
    if (subscriberStatus === "active" && paused) return { key: "paused", label: "Paused" };
    if (subscriberStatus === "active" && rule.status === "active" && !rule.paused) {
        return { key: "active", label: "Active" };
    }
    return { key: "pending", label: "Pending verification" };
}

function ruleTitle(rule) {
    return (rule && (rule.name || rule.brand)) || "Alert";
}

function ruleMeta(rule) {
    const bits = [];
    if (rule.part) bits.push(rule.part);
    if (rule.size || rule.width != null) bits.push(String(rule.size || rule.width));
    if (rule.max_price != null && rule.max_price !== "") bits.push("under $" + Number(rule.max_price).toFixed(2));
    return bits.join(" · ");
}

function ruleTriggers(rule) {
    const bits = [];
    if (rule.alert_on_drop) bits.push("Meaningful drop");
    if (rule.alert_on_low) bits.push("Historical low");
    if (rule.alert_on_stock) bits.push("Verified restock");
    if (rule.alert_on_new) bits.push("Newly listed");
    if (!bits.length) bits.push("New, meaningful drop, or verified restock");
    return bits.join(", ");
}

function describeWatch(draft) {
    draft = draft || {};
    const bits = [];
    if (draft.match === "brand" && draft.brand) bits.push(draft.brand);
    else bits.push(draft.name || draft.brand || "this product");
    if (draft.part) bits.push(draft.part);
    if (draft.size) bits.push(String(draft.size));
    if (String(draft.max_price == null ? "" : draft.max_price).trim() !== "" && Number(draft.max_price) > 0) {
        bits.push("under $" + Number(draft.max_price).toFixed(2));
    }
    return bits.join(" · ");
}

function alertsFailureMessage(result) {
    result = result || {};
    if (result.error === "rate_limited" || result.status === 429) {
        return "Too many requests. Wait a while and try again. Nothing was changed.";
    }
    if (result.error === "turnstile_required") {
        return "The alerts service needs a human check that isn't available on this page. Nothing was saved.";
    }
    if (result.error === "unavailable") return "Email alerts coming soon. Nothing was saved.";
    if (result.error === "network" || result.status === 0) {
        return result.message || "The alerts service could not be reached. Nothing was saved.";
    }
    if (result.status === 401 || result.error === "token_expired") {
        return result.message || "This manage link has expired. Request a new one.";
    }
    return result.message || "Something went wrong. Nothing was saved.";
}

function alertsResult(status, body, extra) {
    const payload = body || {};
    const result = {
        ok: status >= 200 && status < 300,
        status: status,
        error: payload.error || "",
        message: payload.message || "",
        body: payload
    };
    if (extra) {
        Object.keys(extra).forEach(key => { result[key] = extra[key]; });
    }
    return result;
}

function createAlertsMock() {
    const byEmail = new Map();
    const api = { lastPreviewToken: "", lastPreviewKind: "", seq: 1 };

    function findByToken(token, field) {
        if (!token) return null;
        for (const sub of byEmail.values()) {
            if (sub[field] && sub[field] === token) return sub;
        }
        return null;
    }

    function withId(rule) {
        const copy = cleanRule(rule);
        if (!copy.rule_id) copy.rule_id = "r_" + api.seq++;
        return copy;
    }

    function decorate(rule, status) {
        const copy = cleanRule(rule);
        if (status !== "active") copy.status = "pending";
        else if (copy.paused) copy.status = "paused";
        else copy.status = "active";
        return copy;
    }

    function payload(sub) {
        return {
            status: sub.status,
            verified: sub.status === "active",
            email_masked: maskEmail(sub.email),
            consent_version: sub.consentVersion || "",
            rules: (sub.rules || []).map(rule => decorate(rule, sub.status)),
            limits: { max_rules: 10, note_max: 80 }
        };
    }

    function accepted(message) {
        return { status: "accepted", message: message };
    }

    api.peek = function (email) {
        const sub = byEmail.get(normalizeEmail(email));
        if (!sub) return null;
        return {
            status: sub.status,
            verifyToken: sub.verifyToken || "",
            manageToken: sub.manageToken || "",
            rules: payload(sub).rules
        };
    };

    api.handle = function (method, path, options) {
        options = options || {};
        const body = options.body || {};
        const token = options.token || "";
        if (method === "POST" && path === "/subscribe") {
            const email = normalizeEmail(body.email);
            if (body.consent !== true || !validEmail(email)) {
                return alertsResult(400, {
                    error: "invalid_request",
                    message: "Enter an email address and check the consent box. Nothing was saved."
                });
            }
            const rules = Array.isArray(body.rules) ? body.rules.map(cleanRule) : [];
            const problem = validateRules(rules, { requireOne: true });
            if (problem) return alertsResult(400, { error: "invalid_rules", message: problem });
            let sub = byEmail.get(email);
            const verifyToken = "verify_" + api.seq++;
            if (!sub) {
                sub = {
                    email: email,
                    status: "pending",
                    manageToken: "manage_" + api.seq++,
                    verifyToken: verifyToken,
                    consentVersion: body.consent_version || "",
                    rules: rules.map(withId)
                };
                byEmail.set(email, sub);
                api.lastPreviewToken = verifyToken;
                api.lastPreviewKind = "verify";
            } else if (sub.status !== "active") {
                sub.status = "pending";
                sub.verifyToken = verifyToken;
                sub.consentVersion = body.consent_version || sub.consentVersion;
                sub.rules = rules.map(withId);
                api.lastPreviewToken = verifyToken;
                api.lastPreviewKind = "verify";
            } else {
                api.lastPreviewToken = "";
                api.lastPreviewKind = "";
            }
            return alertsResult(202, accepted(ALERTS_ACCEPTED_MESSAGE), {
                previewToken: api.lastPreviewToken,
                previewKind: api.lastPreviewKind
            });
        }
        if (method === "POST" && path === "/verify") {
            const sub = findByToken(body.token, "verifyToken");
            if (!sub) {
                return alertsResult(400, {
                    error: "invalid_token",
                    message: "This confirmation link is invalid or already used."
                });
            }
            sub.status = "active";
            sub.verifyToken = "";
            api.lastPreviewToken = "";
            api.lastPreviewKind = "";
            return alertsResult(200, {
                status: "active",
                manage_token: sub.manageToken,
                email_masked: maskEmail(sub.email)
            });
        }
        if (method === "POST" && path === "/link") {
            const email = normalizeEmail(body.email);
            if (!validEmail(email)) {
                return alertsResult(400, {
                    error: "invalid_request",
                    message: "Enter an email address. Nothing was sent."
                });
            }
            const sub = byEmail.get(email);
            if (sub) {
                sub.manageToken = "manage_" + api.seq++;
                api.lastPreviewToken = sub.manageToken;
                api.lastPreviewKind = "manage";
            } else {
                api.lastPreviewToken = "";
                api.lastPreviewKind = "";
            }
            return alertsResult(202, accepted(ALERTS_LINK_MESSAGE), {
                previewToken: api.lastPreviewToken,
                previewKind: api.lastPreviewKind
            });
        }
        if (path === "/preferences" && (method === "GET" || method === "PUT")) {
            const sub = findByToken(token, "manageToken");
            if (!sub) {
                return alertsResult(401, {
                    error: "token_expired",
                    message: "This manage link has expired. Request a new one."
                });
            }
            if (method === "PUT") {
                const rules = Array.isArray(body.rules) ? body.rules.map(cleanRule) : null;
                const problem = validateRules(rules || [], {});
                if (!rules || problem) {
                    return alertsResult(400, { error: "invalid_rules", message: problem || "Those rules could not be saved." });
                }
                sub.rules = rules.map(withId);
            }
            return alertsResult(200, payload(sub));
        }
        if ((method === "POST" && path === "/unsubscribe") || (method === "DELETE" && path === "/subscriber")) {
            const bearer = findByToken(token, "manageToken");
            const posted = findByToken(body.token, "manageToken");
            const sub = bearer || posted;
            if (!sub) {
                return alertsResult(401, {
                    error: "token_expired",
                    message: "This manage link has expired. Request a new one."
                });
            }
            byEmail.delete(sub.email);
            const message = method === "DELETE"
                ? "Your address and rules were deleted."
                : "You are unsubscribed. We deleted your address and rules.";
            return alertsResult(200, { status: method === "DELETE" ? "deleted" : "unsubscribed", message: message });
        }
        return alertsResult(404, { error: "not_found", message: "That alerts request is not available." });
    };
    return api;
}

async function liveAlertsRequest(config, fetchImpl, method, path, options) {
    options = options || {};
    const headers = { Accept: "application/json" };
    if (options.body) headers["Content-Type"] = "application/json";
    if (options.token) headers.Authorization = "Bearer " + options.token;
    let response;
    try {
        response = await fetchImpl(config.apiBase + path, {
            method: method,
            headers: headers,
            body: options.body ? JSON.stringify(options.body) : undefined,
            credentials: "omit",
            mode: "cors"
        });
    } catch (err) {
        return alertsResult(0, {
            error: "network",
            message: "The alerts service could not be reached. Nothing was saved."
        });
    }
    let body = {};
    try {
        body = await response.json();
    } catch (err) {
        body = {};
    }
    if (response.status === 202) {
        const message = body.message || (path === "/link" ? ALERTS_LINK_MESSAGE : ALERTS_ACCEPTED_MESSAGE);
        return alertsResult(202, Object.assign({ status: "accepted", message: message }, body));
    }
    if (response.ok) return alertsResult(response.status, body);
    return alertsResult(response.status, {
        error: body.error || "error",
        message: body.message || "Something went wrong. Nothing was saved."
    });
}

function createAlertsClient(config, fetchImpl) {
    config = config || { mode: "soon" };
    const mock = config.mode === "mock" ? createAlertsMock() : null;
    const net = fetchImpl || (typeof fetch === "function" ? fetch : null);
    async function request(method, path, options) {
        if (config.mode === "soon") {
            return alertsResult(0, { error: "unavailable", message: "Email alerts coming soon. Nothing was saved." });
        }
        if (config.mode === "mock") return mock.handle(method, path, options || {});
        return liveAlertsRequest(config, net, method, path, options || {});
    }
    return {
        mode: config.mode,
        subscribe(payload) { return request("POST", "/subscribe", { body: payload }); },
        verify(token) { return request("POST", "/verify", { body: { token: token } }); },
        requestLink(payload) { return request("POST", "/link", { body: payload }); },
        getPreferences(token) { return request("GET", "/preferences", { token: token }); },
        putPreferences(token, rules) { return request("PUT", "/preferences", { token: token, body: { rules: (rules || []).map(cleanRule) } }); },
        unsubscribe(token) { return request("POST", "/unsubscribe", { token: token, body: { token: token } }); },
        deleteSubscriber(token) { return request("DELETE", "/subscriber", { token: token }); },
        peek(email) { return mock ? mock.peek(email) : null; },
        lastPreview() {
            if (!mock) return { token: "", kind: "" };
            return { token: mock.lastPreviewToken || "", kind: mock.lastPreviewKind || "" };
        }
    };
}

function alertsEl(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
}

function alertsId(node, id) {
    node.id = id;
    node.setAttribute("id", id);
    return node;
}

function isAlertsOpen() {
    const root = document.getElementById("alertsRoot");
    return !!(alertsUi.open && root && !root.hidden);
}

function setAlertsHash(fragment) {
    alertsUi.writingHash = true;
    const base = (location.pathname || "") + (location.search || "");
    const next = fragment ? base + fragment : base;
    if (typeof history !== "undefined" && history.replaceState) history.replaceState(null, "", next);
    else location.hash = fragment || "";
    alertsUi.writingHash = false;
}

function appendQuickAlert(parent, card) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quick-alert";
    button.textContent = "Alert me";
    button.addEventListener("click", event => {
        if (event.preventDefault) event.preventDefault();
        if (event.stopPropagation) event.stopPropagation();
        const dataset = (card && card.dataset) || {};
        openAlerts({
            draft: alertDraftFromDataset(dataset, card),
            returnFocus: button
        });
    });
    parent.appendChild(button);
}

function mountAlertsNav() {
    if (document.getElementById("navAlerts")) return;
    const group = document.querySelector ? document.querySelector(".topnav-links") : null;
    if (!group) return;
    const button = alertsEl("button", "nav-link", "Alerts");
    button.type = "button";
    alertsId(button, "navAlerts");
    button.setAttribute("aria-haspopup", "dialog");
    button.setAttribute("aria-controls", "alertsRoot");
    button.setAttribute("aria-expanded", "false");
    button.addEventListener("click", () => openAlerts({ returnFocus: button }));
    group.appendChild(button);
}

function ensureAlertsShell() {
    if (document.getElementById("alertsRoot")) return;
    const root = alertsEl("div");
    alertsId(root, "alertsRoot");
    root.hidden = true;
    const panel = alertsEl("div", "alerts-panel");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-labelledby", "alertsTitle");
    panel.tabIndex = -1;
    const head = alertsEl("div", "alerts-head");
    const title = alertsEl("h2", "alerts-title", "Email alerts");
    alertsId(title, "alertsTitle");
    const close = alertsEl("button", "alerts-close", "×");
    close.type = "button";
    alertsId(close, "alertsClose");
    close.setAttribute("aria-label", "Close alerts");
    close.addEventListener("click", event => {
        if (event.preventDefault) event.preventDefault();
        closeAlerts();
    });
    head.append(title, close);
    const error = alertsEl("div", "alerts-error");
    alertsId(error, "alertsError");
    error.setAttribute("role", "alert");
    error.tabIndex = -1;
    const live = alertsEl("div", "alerts-live");
    alertsId(live, "alertsLive");
    live.setAttribute("aria-live", "polite");
    const body = alertsEl("div", "alerts-body");
    alertsId(body, "alertsBody");
    panel.append(head, error, live, body);
    root.appendChild(panel);
    root.addEventListener("click", event => {
        if (event.target === root) closeAlerts();
        else onAlertsClick(event);
    });
    document.body.appendChild(root);
    document.addEventListener("keydown", alertsKeydown);
}

function alertsKeydown(event) {
    if (!isAlertsOpen() || !event || event.key !== "Tab") return;
    const panel = document.querySelector(".alerts-panel");
    if (!panel || !panel.querySelectorAll) return;
    const nodes = panel.querySelectorAll("button, a, input, select, textarea");
    const items = [];
    for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];
        if (node.disabled || node.hidden) continue;
        items.push(node);
    }
    if (!items.length || !panel.contains) return;
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && (active === first || !panel.contains(active))) {
        if (event.preventDefault) event.preventDefault();
        last.focus();
    } else if (!event.shiftKey && active === last) {
        if (event.preventDefault) event.preventDefault();
        first.focus();
    }
}

function focusAlerts(id) {
    const node = (id && document.getElementById(id)) || document.querySelector(".alerts-panel");
    if (node && node.focus) node.focus();
}

function syncAlertsNav() {
    const nav = document.getElementById("navAlerts");
    if (!nav) return;
    nav.setAttribute("aria-expanded", alertsUi.open ? "true" : "false");
}

function closeAlerts() {
    const root = document.getElementById("alertsRoot");
    if (root) root.hidden = true;
    if (document.body && document.body.classList) document.body.classList.remove("alerts-open");
    alertsUi.open = false;
    syncAlertsNav();
    const back = alertsUi.returnFocus;
    alertsUi.returnFocus = null;
    if (back && back.focus) back.focus();
}

function checkedBox(id) {
    const node = document.getElementById(id);
    return !!(node && node.checked);
}

function readRuleForm() {
    const draft = Object.assign({}, alertsUi.draft || blankAlertDraft());
    const brandRadio = document.getElementById("alertsMatchBrand");
    const nameRadio = document.getElementById("alertsMatchName");
    if (brandRadio || nameRadio) draft.match = brandRadio && brandRadio.checked ? "brand" : "name";
    const brand = document.getElementById("alertsBrand");
    if (brand) draft.brand = brand.value;
    const name = document.getElementById("alertsName");
    if (name) draft.name = name.value;
    const part = document.getElementById("alertsPart");
    if (part) draft.part = part.value;
    const size = document.getElementById("alertsSize");
    if (size) draft.size = size.value;
    const price = document.getElementById("alertsPrice");
    if (price) draft.max_price = String(price.value || "").trim();
    if (document.getElementById("alertsDrop")) draft.alert_on_drop = checkedBox("alertsDrop");
    if (document.getElementById("alertsLow")) draft.alert_on_low = checkedBox("alertsLow");
    if (document.getElementById("alertsStock")) draft.alert_on_stock = checkedBox("alertsStock");
    if (document.getElementById("alertsNew")) draft.alert_on_new = checkedBox("alertsNew");
    const note = document.getElementById("alertsNote");
    if (note) draft.note = note.value;
    return draft;
}

function fieldWrap(labelText, input, hint) {
    const wrap = alertsEl("label", "alerts-field");
    wrap.appendChild(alertsEl("span", "", labelText));
    if (input) wrap.appendChild(input);
    if (hint) wrap.appendChild(alertsEl("small", "alerts-hint", hint));
    return wrap;
}

function actionButton(text, className, action, ruleId) {
    const button = alertsEl("button", className, text);
    button.type = "button";
    button.setAttribute("data-action", action);
    if (ruleId) button.setAttribute("data-rule-id", ruleId);
    if (alertsUi.busy) button.disabled = true;
    return button;
}

function textInput(id, value, type) {
    const input = alertsEl("input");
    input.type = type || "text";
    alertsId(input, id);
    input.value = value == null ? "" : String(value);
    return input;
}

function appendMatchFields(form, draft) {
    if (draft.form === "card" && (draft.name || draft.brand)) {
        const group = alertsEl("div", "alerts-match");
        group.setAttribute("role", "radiogroup");
        group.setAttribute("aria-label", "What to watch");
        if (draft.name) {
            const label = alertsEl("label", "alerts-check");
            const input = textInput("alertsMatchName", "", "radio");
            input.name = "alertsMatch";
            input.checked = draft.match !== "brand";
            label.append(input, alertsEl("span", "", " This product: " + draft.name));
            group.appendChild(label);
        }
        if (draft.brand) {
            const label = alertsEl("label", "alerts-check");
            const input = textInput("alertsMatchBrand", "", "radio");
            input.name = "alertsMatch";
            input.checked = draft.match === "brand" || !draft.name;
            const noun = draft.part ? draft.part.toLowerCase() : "products";
            label.append(input, alertsEl("span", "", " Any " + draft.brand + " " + noun));
            group.appendChild(label);
        }
        form.appendChild(group);
        if (draft.store) {
            form.appendChild(alertsEl("p", "alerts-hint", "Opened from the " + draft.store + " listing. A brand watch can match the same product at other stores."));
        }
        return;
    }
    const brand = textInput("alertsBrand", draft.brand || "");
    brand.maxLength = 120;
    form.appendChild(fieldWrap("Brand", brand, "Every word must match. Leave blank if you name one product."));
    const name = textInput("alertsName", draft.name || "");
    name.maxLength = 160;
    form.appendChild(fieldWrap("Product", name, "Optional. Names one product instead of a whole brand."));
}

function appendRuleFields(form, draft) {
    appendMatchFields(form, draft);
    const part = alertsEl("select");
    alertsId(part, "alertsPart");
    ALERTS_PARTS.forEach(value => {
        const option = alertsEl("option", "", value || "Any type");
        option.value = value;
        option.setAttribute("value", value);
        if (value === (draft.part || "")) option.selected = true;
        part.appendChild(option);
    });
    part.value = draft.part || "";
    form.appendChild(fieldWrap("Type", part, ""));
    const size = textInput("alertsSize", draft.size || "");
    size.setAttribute("inputmode", "decimal");
    form.appendChild(fieldWrap("Size", size, "Deck width in inches, or a US shoe size. Leave blank for any size."));
    const price = textInput("alertsPrice", draft.max_price == null ? "" : draft.max_price, "number");
    price.setAttribute("min", "0");
    price.setAttribute("step", "0.01");
    price.setAttribute("inputmode", "decimal");
    const priceHint = draft.form === "card" && draft.max_price !== ""
        ? "Suggested from the current sale price. A match is strictly under this amount. Leave blank to skip the price check."
        : "A match is strictly under this amount. Leave blank to skip the price check.";
    form.appendChild(fieldWrap("Target price", price, priceHint));
    const triggers = alertsEl("fieldset", "alerts-triggers");
    triggers.appendChild(alertsEl("legend", "alerts-legend", "Email me when"));
    [
        ["alertsDrop", "Meaningful drop", "At least $2 or 5% off the previous sale price.", draft.alert_on_drop],
        ["alertsLow", "Historical low", "A qualified all-time low: 3 observations over 7 days.", draft.alert_on_low],
        ["alertsStock", "Verified restock", "Back in stock on reliable evidence, not a missed scan.", draft.alert_on_stock],
        ["alertsNew", "Newly listed", "The product shows up as a new listing.", draft.alert_on_new]
    ].forEach(row => {
        const label = alertsEl("label", "alerts-check");
        const box = textInput(row[0], "", "checkbox");
        box.checked = !!row[3];
        label.append(box, alertsEl("span", "", " " + row[1]));
        triggers.appendChild(label);
        triggers.appendChild(alertsEl("p", "alerts-hint", row[2]));
    });
    triggers.appendChild(alertsEl("p", "alerts-hint", "If none are checked, a match is included when it is newly listed, drops by at least $2 or 5%, or is verified back in stock."));
    form.appendChild(triggers);
    const note = alertsEl("textarea");
    alertsId(note, "alertsNote");
    note.maxLength = 80;
    note.value = draft.note || "";
    note.rows = 2;
    form.appendChild(fieldWrap("Note", note, "Optional. 80 characters. Shown on the digest, not used for matching."));
}

function appendPrivacy(parent) {
    const details = alertsEl("details", "alerts-privacy");
    details.appendChild(alertsEl("summary", "", "Email, confirmation, and unsubscribe"));
    details.appendChild(alertsEl("p", "alerts-hint", "We store the address and these rules until you unsubscribe. Unconfirmed signups are deleted after 7 days. The digest is at most one email a day, and only when a rule matches. The manage link stays in the page address after the # so it is not sent to this site's server. Don't share that link. Stars on this page stay in this browser and never send email."));
    parent.appendChild(details);
}

function mountTurnstile(parent) {
    const config = alertsUi.config || {};
    if (!config.turnstileSiteKey || config.mode !== "live") return;
    const slot = alertsEl("div", "alerts-turnstile");
    alertsId(slot, "alertsTurnstile");
    parent.appendChild(slot);
    if (document.getElementById("alertsTurnstileScript") || !document.head) return;
    const script = document.createElement("script");
    alertsId(script, "alertsTurnstileScript");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
    script.async = true;
    script.defer = true;
    script.addEventListener("load", () => {
        const host = document.getElementById("alertsTurnstile");
        if (!host || !window.turnstile || !window.turnstile.render) return;
        window.turnstile.render(host, {
            sitekey: config.turnstileSiteKey,
            callback: token => { alertsUi.turnstileToken = token || ""; }
        });
    });
    document.head.appendChild(script);
}

function paintSoon(body) {
    body.appendChild(alertsEl("p", "alerts-copy", "Nothing here subscribes you, and nothing is saved. Stars stay in this browser and do not send email. When email alerts are ready, a rule stays off until you confirm your address, and you can unsubscribe in one step."));
    const draft = alertsUi.draft;
    if (draft && (draft.name || draft.brand)) {
        body.appendChild(alertsEl("p", "alerts-copy", "You'd be able to watch: " + describeWatch(draft) + "."));
    }
    appendPrivacy(body);
}

function paintCheck(body) {
    body.appendChild(alertsEl("p", "alerts-hint", "The same reply is shown whether or not this address is already signed up. This page will not turn an alert on until a confirmation link comes back from the alerts service."));
    if (alertsUi.config.mode === "mock" && alertsUi.previewToken) {
        body.appendChild(actionButton("Open preview confirmation", "alerts-secondary", "preview", ""));
        body.appendChild(alertsEl("p", "alerts-hint", "Preview mode did not send email. This opens the confirmation that preview would have emailed."));
    }
    body.appendChild(actionButton("Use a different address", "alerts-secondary", "reset-signup", ""));
}

function paintRelink(body) {
    body.appendChild(alertsEl("p", "alerts-copy", "Request a new manage link. If an account exists, the message arrives shortly. The link belongs in the address bar, after the #."));
    const form = alertsEl("form", "alerts-form");
    alertsId(form, "alertsLinkForm");
    form.noValidate = true;
    form.setAttribute("novalidate", "");
    form.addEventListener("submit", submitLink);
    const email = textInput("alertsLinkEmail", "", "email");
    email.setAttribute("autocomplete", "email");
    email.setAttribute("aria-label", "Email");
    form.appendChild(fieldWrap("Email", email, ""));
    const submit = alertsEl("button", "alerts-primary", alertsUi.busy ? "Sending…" : "Email me a new link");
    submit.type = "submit";
    alertsId(submit, "alertsLinkSubmit");
    if (alertsUi.busy) submit.disabled = true;
    form.appendChild(submit);
    body.appendChild(form);
}

function paintSignup(body) {
    const draft = alertsUi.draft || blankAlertDraft();
    const form = alertsEl("form", "alerts-form");
    alertsId(form, "alertsForm");
    form.noValidate = true;
    form.setAttribute("novalidate", "");
    form.addEventListener("submit", submitSignup);
    form.appendChild(alertsEl("p", "alerts-copy", "At most one email a day, only when a rule matches. It stays off until you confirm the address."));
    appendRuleFields(form, draft);
    const email = textInput("alertsEmail", alertsUi.email || "", "email");
    email.setAttribute("autocomplete", "email");
    email.setAttribute("aria-label", "Email");
    form.appendChild(fieldWrap("Email", email, ""));
    const consent = alertsEl("label", "alerts-check");
    const box = textInput("alertsConsent", "", "checkbox");
    box.checked = !!alertsUi.consent;
    consent.append(box, alertsEl("span", "", " Email me at most one digest a day, only when a rule matches. I can unsubscribe in one step. Nothing is sent until I confirm this address."));
    form.appendChild(consent);
    appendPrivacy(form);
    const actions = alertsEl("div", "alerts-actions");
    const submit = alertsEl("button", "alerts-primary", alertsUi.busy ? "Sending…" : "Email me a confirmation");
    submit.type = "submit";
    alertsId(submit, "alertsSubmit");
    if (alertsUi.busy) submit.disabled = true;
    actions.appendChild(submit);
    actions.appendChild(actionButton("I already confirmed — email me a manage link", "alerts-secondary", "relink", ""));
    form.appendChild(actions);
    mountTurnstile(form);
    body.appendChild(form);
}

function paintEdit(body) {
    const draft = alertsUi.draft || blankAlertDraft();
    const form = alertsEl("form", "alerts-form");
    alertsId(form, "alertsEditForm");
    form.noValidate = true;
    form.setAttribute("novalidate", "");
    form.addEventListener("submit", saveEdit);
    form.appendChild(alertsEl("h3", "alerts-subtitle", draft.rule_id ? "Edit alert" : "Add an alert"));
    appendRuleFields(form, draft);
    const actions = alertsEl("div", "alerts-actions");
    const submit = alertsEl("button", "alerts-primary", alertsUi.busy ? "Saving…" : "Save alert");
    submit.type = "submit";
    alertsId(submit, "alertsSave");
    if (alertsUi.busy) submit.disabled = true;
    actions.appendChild(submit);
    actions.appendChild(actionButton("Cancel", "alerts-secondary", "cancel-edit", ""));
    form.appendChild(actions);
    body.appendChild(form);
}

function paintManage(body) {
    const prefs = alertsUi.prefs || {};
    const active = prefs.status === "active";
    body.appendChild(alertsEl("p", "alerts-copy", active
        ? "This address is confirmed. A rule is on only when it says Active. The digest is at most once a day."
        : "Pending email verification. These rules are saved and are not active. Open the confirmation link before any of them can send mail."));
    if (prefs.email_masked) body.appendChild(alertsEl("p", "alerts-meta", "Address " + prefs.email_masked));
    const rules = prefs.rules || [];
    if (!rules.length) body.appendChild(alertsEl("p", "alerts-copy", "You have no alerts yet."));
    rules.forEach(rule => {
        const card = alertsEl("article", "alerts-rule");
        const badge = ruleBadge(prefs.status, rule);
        card.appendChild(alertsEl("h3", "", ruleTitle(rule)));
        card.appendChild(alertsEl("span", "alerts-status is-" + badge.key, badge.label));
        const meta = [ruleMeta(rule), ruleTriggers(rule)].filter(Boolean).join(" · ");
        if (meta) card.appendChild(alertsEl("p", "alerts-meta", meta));
        if (rule.note) card.appendChild(alertsEl("p", "alerts-meta", rule.note));
        const actions = alertsEl("div", "alerts-actions");
        if (alertsUi.confirmId === rule.rule_id) {
            actions.appendChild(alertsEl("span", "alerts-meta", "Remove this alert?"));
            actions.appendChild(actionButton("Remove", "alerts-danger", "confirm-remove", rule.rule_id));
            actions.appendChild(actionButton("Keep", "alerts-secondary", "cancel-remove", ""));
        } else {
            actions.appendChild(actionButton("Edit", "alerts-secondary", "edit", rule.rule_id));
            const paused = !!rule.paused || rule.status === "paused";
            actions.appendChild(actionButton(paused ? "Resume" : "Pause", "alerts-secondary", "pause", rule.rule_id));
            actions.appendChild(actionButton("Remove", "alerts-danger", "remove", rule.rule_id));
        }
        card.appendChild(actions);
        body.appendChild(card);
    });
    const bar = alertsEl("div", "alerts-actions");
    if (rules.length < 10) bar.appendChild(actionButton("Add an alert", "alerts-primary", "add", ""));
    body.appendChild(bar);
    appendPrivacy(body);
    const danger = alertsEl("div", "alerts-actions");
    if (alertsUi.confirmId === "unsubscribe") {
        danger.appendChild(alertsEl("span", "alerts-meta", "Unsubscribe and delete this address?"));
        danger.appendChild(actionButton("Unsubscribe", "alerts-danger", "confirm-unsubscribe", ""));
        danger.appendChild(actionButton("Keep alerts", "alerts-secondary", "cancel-remove", ""));
    } else {
        danger.appendChild(actionButton("Unsubscribe", "alerts-danger", "unsubscribe", ""));
    }
    body.appendChild(danger);
    body.appendChild(alertsEl("p", "alerts-hint", "Unsubscribing deletes your address and rules right away. Every digest also has a one-click unsubscribe link that does not need this page."));
}

function paintAlerts(focusId) {
    const title = document.getElementById("alertsTitle");
    const live = document.getElementById("alertsLive");
    const error = document.getElementById("alertsError");
    const body = document.getElementById("alertsBody");
    if (!body) return;
    const config = alertsUi.config || { mode: "soon" };
    const managing = config.mode !== "soon" && alertsUi.prefs && alertsUi.token && (alertsUi.view === "manage" || alertsUi.view === "edit");
    if (title) title.textContent = managing ? "Manage alerts" : "Email alerts";
    if (error) error.textContent = alertsUi.error || "";
    if (live) live.textContent = alertsUi.message || "";
    body.replaceChildren();
    if (config.mode === "soon") {
        paintSoon(body);
    } else {
        if (config.mode === "mock") {
            body.appendChild(alertsEl("p", "alerts-banner", "Preview mode. No email is sent."));
        }
        if (alertsUi.view === "check") paintCheck(body);
        else if (alertsUi.view === "relink") paintRelink(body);
        else if (alertsUi.view === "edit" && alertsUi.prefs && alertsUi.token) paintEdit(body);
        else if (alertsUi.view === "manage" && alertsUi.prefs && alertsUi.token) paintManage(body);
        else paintSignup(body);
    }
    if (focusId) focusAlerts(focusId);
}

function ensureClient() {
    const config = alertsPageConfig();
    alertsUi.config = config;
    if (!alertsUi.client || alertsUi.client.mode !== config.mode) alertsUi.client = createAlertsClient(config);
    return config;
}

async function openAlerts(options) {
    options = options || {};
    ensureAlertsShell();
    mountAlertsNav();
    const config = ensureClient();
    const root = document.getElementById("alertsRoot");
    if (options.returnFocus) alertsUi.returnFocus = options.returnFocus;
    else if (!alertsUi.returnFocus && document.activeElement && document.activeElement.focus) {
        alertsUi.returnFocus = document.activeElement;
    }
    if (typeof isQuickOpen === "function" && isQuickOpen() && typeof closeQuickView === "function") {
        let back = null;
        if (typeof quickCard !== "undefined" && quickCard && quickCard.querySelector) back = quickCard.querySelector(".card-more");
        closeQuickView();
        if (back) alertsUi.returnFocus = back;
    }
    alertsUi.open = true;
    if (root) root.hidden = false;
    if (document.body && document.body.classList) document.body.classList.add("alerts-open");
    syncAlertsNav();
    if (config.mode === "soon") {
        alertsUi.view = "signup";
        alertsUi.message = "Email alerts coming soon.";
        alertsUi.error = "";
        if (options.draft) alertsUi.draft = options.draft;
        paintAlerts("alertsClose");
        return;
    }
    if (options.fragment) {
        await openAlertsFragment(options.fragment);
        return;
    }
    alertsUi.error = "";
    if (options.draft && alertsUi.token && alertsUi.prefs) {
        alertsUi.draft = Object.assign(blankAlertDraft(), options.draft, { rule_id: "", paused: false });
        alertsUi.editingId = "";
        alertsUi.view = "edit";
        alertsUi.message = "";
        paintAlerts("alertsSize");
        return;
    }
    if (options.draft) {
        alertsUi.draft = options.draft;
        alertsUi.view = "signup";
        alertsUi.message = "";
        paintAlerts("alertsEmail");
        return;
    }
    if (alertsUi.token && alertsUi.prefs) {
        alertsUi.view = "manage";
        paintAlerts("alertsClose");
        return;
    }
    if (alertsUi.token && !alertsUi.prefs) {
        await loadPreferences();
        return;
    }
    alertsUi.draft = alertsUi.draft || blankAlertDraft();
    alertsUi.view = "signup";
    alertsUi.message = "";
    paintAlerts("alertsEmail");
}

async function openAlertsFragment(fragment) {
    alertsUi.error = "";
    alertsUi.message = "Checking this link…";
    alertsUi.view = "manage";
    paintAlerts();
    if (fragment.purpose === "verify" || fragment.purpose === "auto") {
        const result = await alertsUi.client.verify(fragment.token);
        if (result.ok) {
            const manage = manageTokenFromVerify(result.body);
            if (!manage) {
                alertsUi.error = "The confirmation response did not include a manage token. Nothing is marked active.";
                alertsUi.message = "";
                alertsUi.view = "relink";
                paintAlerts("alertsError");
                return;
            }
            alertsUi.token = manage;
            setAlertsHash("#manage=" + encodeURIComponent(manage));
            await loadPreferences();
            return;
        }
        if (fragment.purpose === "verify") {
            alertsUi.token = "";
            alertsUi.prefs = null;
            alertsUi.error = alertsFailureMessage(result);
            alertsUi.message = "";
            alertsUi.view = "relink";
            paintAlerts("alertsError");
            return;
        }
    }
    alertsUi.token = fragment.token;
    const loaded = await loadPreferences();
    if (!loaded && fragment.purpose === "auto") {
        alertsUi.view = "relink";
        paintAlerts("alertsLinkEmail");
    }
}

async function loadPreferences() {
    const result = await alertsUi.client.getPreferences(alertsUi.token);
    if (!result.ok) {
        alertsUi.prefs = null;
        alertsUi.view = "relink";
        alertsUi.error = alertsFailureMessage(result);
        alertsUi.message = "";
        paintAlerts("alertsError");
        return false;
    }
    alertsUi.prefs = result.body || {};
    alertsUi.view = "manage";
    alertsUi.error = "";
    alertsUi.confirmId = "";
    alertsUi.message = alertsUi.prefs.status === "active"
        ? "Email confirmed. A rule is on only when it says Active."
        : "Pending email verification. Nothing is active until you confirm.";
    paintAlerts("alertsTitle");
    return true;
}

async function submitSignup(event) {
    if (event && event.preventDefault) event.preventDefault();
    if (alertsUi.busy || !alertsUi.client || alertsUi.config.mode === "soon") return;
    const draft = readRuleForm();
    alertsUi.draft = draft;
    const emailNode = document.getElementById("alertsEmail");
    const email = emailNode ? String(emailNode.value || "").trim() : "";
    alertsUi.email = email;
    alertsUi.consent = checkedBox("alertsConsent");
    const rule = ruleFromDraft(draft);
    const problem = validateSignup(email, checkedBox("alertsConsent"), [rule]);
    if (problem) {
        alertsUi.error = problem;
        alertsUi.message = "";
        paintAlerts("alertsError");
        return;
    }
    alertsUi.busy = true;
    alertsUi.error = "";
    const button = document.getElementById("alertsSubmit");
    if (button) {
        button.disabled = true;
        button.textContent = "Sending…";
    }
    let result;
    try {
        result = await alertsUi.client.subscribe({
            email: email,
            rules: [rule],
            consent: true,
            consent_version: alertsUi.config.consentVersion,
            turnstile_token: alertsUi.turnstileToken || ""
        });
    } catch (err) {
        result = alertsResult(0, { error: "network", message: "The alerts service could not be reached. Nothing was saved." });
    }
    alertsUi.busy = false;
    if (result.status === 202) {
        alertsUi.view = "check";
        alertsUi.message = (result.body && result.body.message) || ALERTS_ACCEPTED_MESSAGE;
        alertsUi.error = "";
        alertsUi.previewToken = result.previewToken || "";
        alertsUi.previewKind = result.previewKind || "";
        paintAlerts("alertsLive");
        return;
    }
    alertsUi.error = alertsFailureMessage(result);
    alertsUi.message = "";
    paintAlerts("alertsError");
}

async function submitLink(event) {
    if (event && event.preventDefault) event.preventDefault();
    if (alertsUi.busy || !alertsUi.client) return;
    const emailNode = document.getElementById("alertsLinkEmail");
    const email = emailNode ? String(emailNode.value || "").trim() : "";
    if (!validEmail(email)) {
        alertsUi.error = "Enter the email address that should get the digest. Nothing was sent.";
        alertsUi.message = "";
        paintAlerts("alertsError");
        return;
    }
    alertsUi.busy = true;
    alertsUi.error = "";
    let result;
    try {
        result = await alertsUi.client.requestLink({
            email: email,
            turnstile_token: alertsUi.turnstileToken || ""
        });
    } catch (err) {
        result = alertsResult(0, { error: "network", message: "The alerts service could not be reached. Nothing was sent." });
    }
    alertsUi.busy = false;
    if (result.status === 202) {
        alertsUi.view = "check";
        alertsUi.message = (result.body && result.body.message) || ALERTS_LINK_MESSAGE;
        alertsUi.error = "";
        alertsUi.previewToken = result.previewToken || "";
        alertsUi.previewKind = result.previewKind || "";
        paintAlerts("alertsLive");
        return;
    }
    alertsUi.error = alertsFailureMessage(result);
    paintAlerts("alertsError");
}

async function saveEdit(event) {
    if (event && event.preventDefault) event.preventDefault();
    if (alertsUi.busy || !alertsUi.prefs) return;
    const draft = readRuleForm();
    const rule = ruleFromDraft(draft);
    const existing = (alertsUi.prefs.rules || []).map(cleanRule);
    let rules;
    if (draft.rule_id) {
        rules = existing.map(item => item.rule_id === draft.rule_id ? rule : item);
    } else {
        rules = existing.concat([rule]);
    }
    const problem = validateRules(rules, {});
    if (problem) {
        alertsUi.error = problem;
        paintAlerts("alertsError");
        return;
    }
    await putRules(rules);
}

async function putRules(rules) {
    alertsUi.busy = true;
    alertsUi.error = "";
    let result;
    try {
        result = await alertsUi.client.putPreferences(alertsUi.token, rules);
    } catch (err) {
        result = alertsResult(0, { error: "network", message: "The alerts service could not be reached. Nothing was changed." });
    }
    alertsUi.busy = false;
    if (!result.ok) {
        alertsUi.error = alertsFailureMessage(result);
        if (result.status === 401) {
            alertsUi.prefs = null;
            alertsUi.view = "relink";
        }
        paintAlerts("alertsError");
        return;
    }
    alertsUi.prefs = result.body || {};
    alertsUi.view = "manage";
    alertsUi.confirmId = "";
    alertsUi.message = alertsUi.prefs.status === "active"
        ? "Saved. A rule is on only when it says Active."
        : "Saved. Pending email verification — nothing is active yet.";
    alertsUi.error = "";
    paintAlerts("alertsLive");
}

function ruleById(id) {
    const rules = (alertsUi.prefs && alertsUi.prefs.rules) || [];
    for (let i = 0; i < rules.length; i++) {
        if (rules[i].rule_id === id) return rules[i];
    }
    return null;
}

async function togglePause(id) {
    const current = (alertsUi.prefs && alertsUi.prefs.rules) || [];
    const rules = current.map(rule => {
        const copy = cleanRule(rule);
        if (copy.rule_id === id) {
            if (copy.paused) delete copy.paused;
            else copy.paused = true;
        }
        return copy;
    });
    await putRules(rules);
}

async function removeRule(id) {
    const current = (alertsUi.prefs && alertsUi.prefs.rules) || [];
    await putRules(current.filter(rule => rule.rule_id !== id).map(cleanRule));
}

async function unsubscribeAlerts() {
    if (!alertsUi.client || alertsUi.busy) return;
    alertsUi.busy = true;
    alertsUi.error = "";
    let result;
    try {
        result = await alertsUi.client.unsubscribe(alertsUi.token);
    } catch (err) {
        result = alertsResult(0, { error: "network", message: "The alerts service could not be reached. Nothing was changed." });
    }
    alertsUi.busy = false;
    if (!result.ok) {
        alertsUi.error = alertsFailureMessage(result);
        paintAlerts("alertsError");
        return;
    }
    alertsUi.token = "";
    alertsUi.prefs = null;
    alertsUi.confirmId = "";
    alertsUi.previewToken = "";
    alertsUi.draft = blankAlertDraft();
    alertsUi.view = "signup";
    setAlertsHash("");
    alertsUi.message = (result.body && result.body.message) || "You are unsubscribed. We deleted your address and rules.";
    alertsUi.error = "";
    paintAlerts("alertsLive");
}

async function confirmPreview() {
    if (!alertsUi.config || alertsUi.config.mode !== "mock" || !alertsUi.previewToken) return;
    if (alertsUi.previewKind === "manage") {
        alertsUi.token = alertsUi.previewToken;
        alertsUi.previewToken = "";
        setAlertsHash("#manage=" + encodeURIComponent(alertsUi.token));
        await loadPreferences();
        return;
    }
    const result = await alertsUi.client.verify(alertsUi.previewToken);
    alertsUi.previewToken = "";
    if (!result.ok) {
        alertsUi.error = alertsFailureMessage(result);
        alertsUi.view = "check";
        paintAlerts("alertsError");
        return;
    }
    const manage = manageTokenFromVerify(result.body);
    if (!manage) {
        alertsUi.error = "The confirmation response did not include a manage token. Nothing is marked active.";
        paintAlerts("alertsError");
        return;
    }
    alertsUi.token = manage;
    setAlertsHash("#manage=" + encodeURIComponent(manage));
    await loadPreferences();
}

function onAlertsClick(event) {
    const target = event && event.target;
    if (!target || !target.closest) return;
    const button = target.closest("[data-action]");
    if (!button) return;
    const root = document.getElementById("alertsRoot");
    if (!root || (root.contains && !root.contains(button))) return;
    if (event.preventDefault) event.preventDefault();
    const action = button.getAttribute("data-action");
    const id = button.getAttribute("data-rule-id") || "";
    if (action === "relink") {
        alertsUi.view = "relink";
        alertsUi.error = "";
        alertsUi.message = "";
        paintAlerts("alertsLinkEmail");
    } else if (action === "reset-signup") {
        alertsUi.view = "signup";
        alertsUi.previewToken = "";
        alertsUi.error = "";
        alertsUi.message = "";
        paintAlerts("alertsEmail");
    } else if (action === "preview") {
        confirmPreview();
    } else if (action === "add") {
        alertsUi.draft = blankAlertDraft();
        alertsUi.editingId = "";
        alertsUi.view = "edit";
        alertsUi.error = "";
        alertsUi.message = "";
        paintAlerts("alertsBrand");
    } else if (action === "edit") {
        const rule = ruleById(id);
        if (!rule) return;
        alertsUi.draft = draftFromRule(rule);
        alertsUi.editingId = id;
        alertsUi.view = "edit";
        alertsUi.error = "";
        alertsUi.message = "";
        paintAlerts("alertsBrand");
    } else if (action === "pause") {
        togglePause(id);
    } else if (action === "remove") {
        alertsUi.confirmId = id;
        paintAlerts();
    } else if (action === "cancel-remove" || action === "cancel-edit") {
        alertsUi.confirmId = "";
        alertsUi.view = "manage";
        alertsUi.error = "";
        paintAlerts();
    } else if (action === "confirm-remove") {
        removeRule(id);
    } else if (action === "unsubscribe") {
        alertsUi.confirmId = "unsubscribe";
        paintAlerts();
    } else if (action === "confirm-unsubscribe") {
        unsubscribeAlerts();
    }
}

function wireAlerts() {
    if (alertsUi.wired) return;
    alertsUi.wired = true;
    mountAlertsNav();
    ensureAlertsShell();
    if (typeof window !== "undefined" && window.addEventListener) {
        window.addEventListener("hashchange", () => {
            if (alertsUi.writingHash) return;
            const parsed = readAlertsFragment(location.hash || "");
            if (parsed) openAlerts({ fragment: parsed });
        });
    }
    const parsed = readAlertsFragment((typeof location !== "undefined" && location.hash) || "");
    if (parsed) openAlerts({ fragment: parsed });
}

/* ALERTS_UI_END */
