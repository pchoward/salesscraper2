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
    // New, price drops, hit lowest, and disappeared always use the previous
    // daily scrape (data-added, data-drop, data-hitlow, and the gone count).
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
    sortKey: "rank",
    sortDir: "asc",
    search: ""
};

const STAR_KEY = "salesscraper2.stars";
const VIEWS_KEY = "salesscraper2.views";
const LAST_VISIT_KEYS = [
    "salesscraper2.snapshot",
    "salesscraper2.lastVisit",
    "salesscraper2.last-visit",
    "salesscraper2.visit",
    "salesscraper2.visitMode"
];
const RETIRED_VISIT_PARAMS = { baseline: 1, visit: 1, visitmode: 1, since: 1 };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
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

// Drop leftover last-visit snapshots. Stars, saved views, layout, and open
// filter sections live under other keys and are left alone.
function forgetLastVisit() {
    try {
        LAST_VISIT_KEYS.forEach(key => localStorage.removeItem(key));
    } catch (err) {
        /* private mode should not break the page */
    }
}

// Previous daily scrape. Visit snapshots are not a baseline.
function scrapeBaseline(row) {
    const data = (row && row.dataset) || {};
    return {
        added: data.added === "1",
        drop: data.drop === "1",
        low: data.hitlow === "1"
    };
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
            if (!discountNode.dataset.baseTitle) discountNode.dataset.baseTitle = discountNode.title || "";
            if (!discountNode.dataset.baseClass) {
                discountNode.dataset.baseClass = ["high", "medium", "low", "none"].filter(name => discountNode.classList.contains(name)).join(" ");
            }
            ["high", "medium", "low", "none"].forEach(name => discountNode.classList.remove(name));
            if (!offer) {
                discountNode.textContent = discountNode.dataset.baseText;
                if (discountNode.dataset.baseTitle) discountNode.title = discountNode.dataset.baseTitle;
                String(discountNode.dataset.baseClass || "").split(/\s+/).filter(Boolean).forEach(name => discountNode.classList.add(name));
                return;
            }
            const percent = rowDiscount(node);
            const klass = percent == null ? "none" : percent >= 40 ? "high" : percent >= 25 ? "medium" : "low";
            discountNode.classList.add(klass);
            const claimed = discountNode.classList.contains("card-off");
            if (claimed) {
                discountNode.title = percent == null
                    ? "This store did not publish a list price, so there is no claimed discount."
                    : "Store's claimed discount versus its list price, not a tracked market price.";
                discountNode.textContent = percent == null ? "No discount info" : Math.round(percent) + "% vs list";
            } else {
                discountNode.textContent = percent == null ? "N/A" : Math.round(percent) + "%";
            }
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

// A zero count is hidden. The option stays when it is selected, or it is the
// group's "all" choice, so it can still be cleared. Search-hidden brands stay
// out of the empty check too.
function facetShown(node) {
    if (!node) return false;
    if (node.hidden) return false;
    if (node.hasAttribute && node.hasAttribute("hidden")) return false;
    if (node.classList && (node.classList.contains("is-unavailable") || node.classList.contains("is-search-hide"))) return false;
    return true;
}

function markFacetOption(node, count, keep) {
    const show = count > 0 || !!keep;
    node.classList.toggle("is-zero", count === 0);
    node.classList.toggle("is-unavailable", !show);
    setHidden(node, !show);
    return show;
}

function syncFacetEmpty(container, selector, message) {
    if (!container || !container.querySelector) return;
    const items = Array.from(container.querySelectorAll(selector));
    const note = container.querySelector(".filter-empty");
    if (!items.length || items.some(facetShown)) {
        if (note) setHidden(note, true);
        return;
    }
    let empty = note;
    if (!empty) {
        empty = document.createElement("p");
        empty.className = "filter-empty";
        container.appendChild(empty);
    }
    empty.textContent = message;
    setHidden(empty, false);
}

function filterBrandList(query) {
    const facet = document.getElementById("brandFacet");
    const text = String(query || "").trim().toLowerCase();
    if (facet) facet.classList.toggle("is-searching", text.length > 0);
    document.querySelectorAll("#brandList .facet-value").forEach(node => {
        const brand = (node.getAttribute("data-brand") || "").toLowerCase();
        const name = node.querySelector(".facet-name");
        const label = ((name && name.textContent) || node.textContent || "").toLowerCase();
        const match = !text || (brand !== "all" && (brand.includes(text) || label.includes(text)));
        node.classList.toggle("is-search-hide", !match);
    });
    syncFacetEmpty(document.getElementById("brandList"), ".facet-value", "No matching brands");
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
    if (!select || !select.options) return;
    // Firefox ignores hidden and display on <option>, so a zero choice is
    // taken out of the list. The pool keeps it so a later filter can put it back.
    if (!select._facetPool) select._facetPool = Array.from(select.options);
    const pool = select._facetPool;
    const current = select.value || "";
    pool.forEach(option => {
        if (!option.value || option.value === "all") return;
        const count = counts[option.value] || 0;
        let label = option.getAttribute("data-label");
        if (!label) {
            label = String(option.textContent || "").replace(/\s*\(\d+\)\s*$/, "");
            option.setAttribute("data-label", label);
        }
        option.textContent = label + " (" + count + ")";
        const keep = count > 0 || option.value === current;
        option.disabled = false;
        if (!keep) {
            if (option.parentNode === select) select.removeChild(option);
        } else if (option.parentNode !== select) {
            select.appendChild(option);
        }
    });
    pool.forEach(option => {
        if (option.parentNode === select) select.appendChild(option);
    });
    if (current && pool.some(option => option.value === current)) select.value = current;
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
        node.setAttribute("data-count", String(count));
        const on = node.getAttribute("aria-pressed") === "true";
        markFacetOption(node, count, on);
    });
    document.querySelectorAll("#sizeFilters .width-chip").forEach(node => {
        let count = 0;
        widthGroupIds(node).forEach(id => { count += widthCounts[id] || 0; });
        const slot = node.querySelector(".width-count");
        if (slot) slot.textContent = String(count);
        node.setAttribute("data-count", String(count));
        const on = node.getAttribute("aria-pressed") === "true" || node.classList.contains("is-partial");
        markFacetOption(node, count, on);
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
            node.setAttribute("data-count", String(count));
            const on = (state[facet.stateKey] || []).indexOf(value) >= 0;
            node.classList.toggle("active", on);
            node.setAttribute("aria-pressed", on ? "true" : "false");
            // Shoe and deck sizes only count tokens already stored on the row.
            // Those are the in-stock sizes; a size named in the title is not added.
            markFacetOption(node, count, on);
        });
        syncFacetEmpty(document.getElementById(facet.section), ".spec-chip", "No options match");
    });
    syncFacetEmpty(document.getElementById("sizeFilters"), ".width-chip", "No sizes match");
    syncFacetEmpty(document.getElementById("brandList"), ".facet-value", "No matching brands");
    syncFacetEmpty(document.getElementById("dealTypes"), ".kind-btn", "No deal types match");
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
    const search = Object.prototype.hasOwnProperty.call(over, "search") ? over.search : state.search;
    if (search && !hay.includes(String(search).toLowerCase())) return false;
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
    const priceMin = Object.prototype.hasOwnProperty.call(over, "priceMin") ? over.priceMin : state.priceMin;
    const priceMax = Object.prototype.hasOwnProperty.call(over, "priceMax") ? over.priceMax : state.priceMax;
    if (priceMin != null && !(price >= priceMin)) return false;
    if (priceMax != null && !(price <= priceMax)) return false;
    const discountMin = Object.prototype.hasOwnProperty.call(over, "discountMin") ? over.discountMin : state.discountMin;
    const discountMax = Object.prototype.hasOwnProperty.call(over, "discountMax") ? over.discountMax : state.discountMax;
    if (discountMin != null || discountMax != null) {
        const discount = rowDiscount(row);
        if (discount == null) return false;
        if (discountMin != null && discount < discountMin) return false;
        if (discountMax != null && discount > discountMax) return false;
    }
    const score = parseFloat(row.dataset.score);
    const scoreMin = Object.prototype.hasOwnProperty.call(over, "scoreMin") ? over.scoreMin : state.scoreMin;
    const scoreMax = Object.prototype.hasOwnProperty.call(over, "scoreMax") ? over.scoreMax : state.scoreMax;
    if (scoreMin != null && !(score >= scoreMin)) return false;
    if (scoreMax != null && !(score <= scoreMax)) return false;
    const watching = Object.prototype.hasOwnProperty.call(over, "watching") ? over.watching : state.watching;
    if (watching && row.dataset.starred !== "1") return false;
    const kinds = Object.prototype.hasOwnProperty.call(over, "kinds") ? over.kinds : state.kinds;
    if (!kindMatch(row, kinds)) return false;
    const highlights = Object.prototype.hasOwnProperty.call(over, "highlights") ? over.highlights : state.highlights;
    if (highlights && row.dataset.highlight !== "1") return false;
    const interval = over.interval != null ? over.interval : state.dropInterval;
    if (!dropInInterval(row, interval)) return false;
    const cardNew = Object.prototype.hasOwnProperty.call(over, "cardNew") ? over.cardNew : state.cardNew;
    const cardDrop = Object.prototype.hasOwnProperty.call(over, "cardDrop") ? over.cardDrop : state.cardDrop;
    const cardLow = Object.prototype.hasOwnProperty.call(over, "cardLow") ? over.cardLow : state.cardLow;
    if (cardNew && row.dataset.added !== "1") return false;
    if (cardDrop && row.dataset.drop !== "1") return false;
    if (cardLow && row.dataset.lowest !== "1") return false;
    const baseline = scrapeBaseline(row);
    const change = over.change != null ? over.change : state.change;
    if (change === "new" && !baseline.added) return false;
    if (change === "drop" && !baseline.drop) return false;
    if (change === "lowest" && !baseline.low) return false;
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
    paintEmptyState();
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
        markFacetOption(button, intervalCounts[key] || 0, key === "all" || on);
    });
    document.querySelectorAll("#dealTypes [data-kind]").forEach(button => {
        const key = button.getAttribute("data-kind") || "";
        const slot = button.querySelector(".facet-count");
        if (slot) slot.textContent = "(" + (kindCounts[key] || 0) + ")";
        const on = key === "watch" ? !!state.watching : key === "highlights" ? !!state.highlights : (state.kinds || []).indexOf(key) >= 0;
        button.setAttribute("aria-pressed", on ? "true" : "false");
        markFacetOption(button, kindCounts[key] || 0, on);
    });
    document.querySelectorAll("#categoryStrip [data-part]").forEach(button => {
        const part = button.getAttribute("data-part") || "all";
        const count = part === "all" ? categoryAll : (categoryCounts[part] || 0);
        const slot = button.querySelector(".cat-count");
        if (slot) slot.textContent = String(count);
        const on = (state.part || "Decks") === part;
        button.setAttribute("aria-pressed", on ? "true" : "false");
        markFacetOption(button, count, part === "all" || on);
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
        node.setAttribute("data-count", String(count));
        markFacetOption(node, count, value === "all" || on);
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

function shownQuickChips(root) {
    return Array.from(root.querySelectorAll(":scope > .quick-chip")).filter(facetShown);
}

function syncNavMore(cluster) {
    const count = shownQuickChips(cluster.list).length;
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
                    chips: shownQuickChips(cluster.row).map(chip => ({
                        value: chip.getAttribute("data-store") || chip.getAttribute("data-part") || "",
                        pressed: chip.getAttribute("aria-pressed") === "true",
                    })),
                })));
                if (!choice) return;
                const cluster = clusters[choice.cluster];
                const chip = shownQuickChips(cluster.row)[choice.index];
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
    const line = document.getElementById("changeLine");
    const prefix = document.getElementById("changePrefix");
    const added = line ? parseInt(line.dataset.new || "0", 10) : 0;
    const drop = line ? parseInt(line.dataset.drops || "0", 10) : 0;
    const low = line ? parseInt(line.dataset.lows || "0", 10) : 0;
    const gone = line ? parseInt(line.dataset.gone || "0", 10) : 0;
    if (prefix) prefix.textContent = "vs previous scrape";
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
        else if (RETIRED_VISIT_PARAMS[key]) {
            /* Old last-visit links. Ignore the param and keep the rest. */
        }
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
    const options = node._facetPool || Array.from(node.options || []);
    let match = options.find(option => option.value === value);
    if (!match && id === "brandSelect" && value) {
        match = options.find(option => brandSame(option.value, value));
    }
    if (match) {
        if (match.parentNode !== node) node.appendChild(match);
        node.value = match.value;
    } else node.value = "all";
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

let filterOrder = [];
let filterLabels = {};

function withoutIds(list, drop) {
    const gone = {};
    (drop || []).forEach(id => { gone[id] = true; });
    return (list || []).filter(id => !gone[id]);
}

function clearField(id) {
    const node = document.getElementById(id);
    if (node) node.value = "";
    applyFilters();
}

function collectFilterActions() {
    const entries = [];
    function add(key, label, clear, lift, chip) {
        entries.push({
            key: key,
            label: label,
            clear: clear,
            lift: lift || {},
            chip: chip !== false
        });
    }
    if (state.search) {
        add("search", "Search: " + state.search, () => {
            const node = document.getElementById("searchInput");
            if (node) node.value = "";
            state.search = "";
            applyFilters();
        }, { search: "" }, false);
    }
    if (state.store !== "all") add("store", "Store: " + state.store, () => filterByStore("all"), { store: "all" });
    if (state.part === "Decks") {
        add("part", "Decks", () => filterByPart("all"), { part: "all" }, false);
    } else if (state.part) {
        const typeLabel = state.part === "all" ? "Type: All types" : "Type: " + state.part;
        add("part", typeLabel, () => filterByPart("Decks"), { part: "Decks" });
    }
    if (state.brand !== "all") {
        add("brand", state.brand, () => {
            setSelect("brandSelect", "all");
            state.brand = "all";
            applyFilters();
        }, { brand: "all" });
    }
    const covered = {};
    if (specKeyActive("widths")) {
        document.querySelectorAll("#sizeFilters .width-chip").forEach(node => {
            const ids = widthGroupIds(node);
            if (!ids.length || !ids.every(id => (state.widths || []).indexOf(id) >= 0)) return;
            ids.forEach(id => { covered[id] = true; });
            const labelNode = node.querySelector(".width-label");
            const label = labelNode ? labelNode.textContent : ids.join(", ");
            add("width:" + ids.join(","), label, () => toggleWidthGroup(node), { widths: withoutIds(state.widths, ids) });
        });
        (state.widths || []).forEach(id => {
            if (covered[id]) return;
            const range = widthRanges().find(item => item.id === id);
            add("width:" + id, range ? range.label : id, () => toggleWidthRange(id), { widths: withoutIds(state.widths, [id]) });
        });
    }
    if (state.priceMin != null) add("min", "Min $" + numText(state.priceMin), () => clearField("priceMin"), { priceMin: null });
    if (state.priceMax != null) add("max", "Max $" + numText(state.priceMax), () => clearField("priceMax"), { priceMax: null });
    if (state.discountMin != null) {
        add("discount", numText(state.discountMin) + "% off or more", () => clearField("discountMin"), { discountMin: null });
    }
    if (state.discountMax != null) {
        add("discountmax", numText(state.discountMax) + "% off or less", () => clearField("discountMax"), { discountMax: null });
    }
    if (state.dropInterval && state.dropInterval !== "all") {
        const labels = { day: "Day", week: "Week", month: "Month", quarter: "3 Months" };
        add("interval", "Drop: " + (labels[state.dropInterval] || state.dropInterval), () => setDropInterval("all"), { interval: "all" });
    }
    (state.kinds || []).forEach(kind => {
        const labels = { new: "New", drop: "Price drop", low: "All-time low", back: "Back in stock", hot: "Hot" };
        add("kind:" + kind, labels[kind] || kind, () => toggleDealType(kind), {
            kinds: (state.kinds || []).filter(item => item !== kind)
        });
    });
    if (state.scoreMin != null) add("scoremin", "Score " + numText(state.scoreMin) + "+", () => clearField("scoreMin"), { scoreMin: null });
    if (state.scoreMax != null) add("scoremax", "Score ≤ " + numText(state.scoreMax), () => clearField("scoreMax"), { scoreMax: null });
    if (specKeyActive("length") && state.length !== "all") {
        add("length", "Length " + state.length, () => {
            setSelect("lengthSelect", "all");
            state.length = "all";
            applyFilters();
        }, { length: "all" });
    }
    if (specKeyActive("wheelbase") && state.wheelbase !== "all") {
        add("wheelbase", "Wheelbase " + state.wheelbase, () => {
            setSelect("wheelbaseSelect", "all");
            state.wheelbase = "all";
            applyFilters();
        }, { wheelbase: "all" });
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
            const lift = {};
            lift[facet.stateKey] = (state[facet.stateKey] || []).filter(item => item !== value);
            add("spec:" + facet.stateKey + ":" + value, specLabels[facet.stateKey](value), () => toggleSpec(facet.stateKey, value), lift);
        });
    });
    if (state.highlights) add("highlights", "Highlights", () => toggleDealType("highlights"), { highlights: false });
    if (state.watching) add("watching", "Watching", () => toggleWatching(), { watching: false });
    if (state.cardNew) add("added", "New deals", () => toggleCard("new"), { cardNew: false });
    if (state.cardDrop) add("dropped", "Price drops", () => toggleCard("drop"), { cardDrop: false });
    if (state.cardLow) add("low", "All-time lows", () => toggleCard("lowest"), { cardLow: false });
    if (state.change === "new") add("change", "New since the previous scrape", () => setChange("all"), { change: "all" });
    if (state.change === "drop") add("change", "Price drops since the previous scrape", () => setChange("all"), { change: "all" });
    if (state.change === "lowest") add("change", "Hit lowest since the previous scrape", () => setChange("all"), { change: "all" });
    if (state.change === "removed") add("change", "Deals disappeared", () => setChange("all"), { change: "all" });
    return entries;
}

function rememberFilterOrder(entries) {
    const live = {};
    (entries || []).forEach(entry => { live[entry.key] = entry.label; });
    filterOrder = filterOrder.filter(key => Object.prototype.hasOwnProperty.call(live, key));
    (entries || []).forEach(entry => {
        const known = filterOrder.indexOf(entry.key);
        const changed = filterLabels[entry.key] !== entry.label;
        if (known < 0 || changed) {
            if (known >= 0) filterOrder.splice(known, 1);
            filterOrder.push(entry.key);
        }
        filterLabels[entry.key] = entry.label;
    });
    Object.keys(filterLabels).forEach(key => {
        if (!Object.prototype.hasOwnProperty.call(live, key)) delete filterLabels[key];
    });
    return filterOrder.slice();
}

function chooseEmptyResets(entries, revealed, order) {
    const list = entries || [];
    const scores = revealed || {};
    if (!list.length) return { last: null, tight: null, same: true };
    const byKey = {};
    list.forEach(entry => { byKey[entry.key] = entry; });
    const ordered = (order || []).filter(key => byKey[key]);
    list.forEach(entry => {
        if (ordered.indexOf(entry.key) < 0) ordered.push(entry.key);
    });
    const last = byKey[ordered[ordered.length - 1]] || list[list.length - 1];
    let tight = list[0];
    list.forEach(entry => {
        if ((scores[entry.key] || 0) > (scores[tight.key] || 0)) tight = entry;
    });
    if (last && tight && tight.key === last.key && list.length > 1) {
        const alt = list.filter(entry => entry.key !== last.key)
            .sort((a, b) => (scores[b.key] || 0) - (scores[a.key] || 0))[0];
        if (alt && (scores[alt.key] || 0) === (scores[tight.key] || 0)) tight = alt;
    }
    return { last: last, tight: tight, same: !last || !tight || last.key === tight.key };
}

function emptyResetPlan(entries, revealed, order) {
    const list = entries || [];
    if (!list.length) {
        return { summary: "", buttons: [{ action: "clear", label: "Clear all" }] };
    }
    const choice = chooseEmptyResets(list, revealed, order);
    const buttons = [];
    if (!choice.last || choice.same) {
        const target = choice.last || choice.tight;
        if (target) buttons.push({ action: "remove", key: target.key, label: "Remove " + target.label });
    } else {
        buttons.push({ action: "remove", key: choice.last.key, label: "Remove last: " + choice.last.label });
        if (choice.tight) buttons.push({ action: "remove", key: choice.tight.key, label: "Remove tightest: " + choice.tight.label });
    }
    buttons.push({ action: "clear", label: "Clear all" });
    return { summary: list.map(entry => entry.label).join(", "), buttons: buttons };
}

function goneRows() {
    return Array.from(document.querySelectorAll("#goneTable tbody tr"));
}

function goneRowMatches(row, over) {
    const lift = over || {};
    const search = Object.prototype.hasOwnProperty.call(lift, "search") ? lift.search : state.search;
    const store = lift.store != null ? lift.store : state.store;
    const part = lift.part != null ? lift.part : state.part;
    const brand = lift.brand != null ? lift.brand : state.brand;
    const priceMin = Object.prototype.hasOwnProperty.call(lift, "priceMin") ? lift.priceMin : state.priceMin;
    const priceMax = Object.prototype.hasOwnProperty.call(lift, "priceMax") ? lift.priceMax : state.priceMax;
    const hay = (row.dataset.search || "").toLowerCase();
    if (search && !hay.includes(String(search).toLowerCase())) return false;
    if (store !== "all" && (row.dataset.store || "") !== store) return false;
    if (part !== "all" && (row.dataset.part || "") !== part) return false;
    if (brand !== "all" && !brandSame(row.dataset.brand, brand)) return false;
    const price = parseFloat(row.dataset.price);
    if (priceMin != null && !(price >= priceMin)) return false;
    if (priceMax != null && !(price <= priceMax)) return false;
    return true;
}

function revealCount(entry, mode) {
    let count = 0;
    if (mode === "gone") {
        goneRows().forEach(row => {
            if (goneRowMatches(row, entry.lift)) count += 1;
        });
        return count;
    }
    dealRows().forEach(row => {
        if (rowMatches(row, entry.lift)) count += 1;
    });
    return count;
}

function visibleDealCount() {
    let count = 0;
    dealRows().forEach(row => {
        if (!row.classList.contains("filtered-out")) count += 1;
    });
    return count;
}

function fillEmpty(node, plan, entries, title) {
    node.hidden = false;
    node.replaceChildren();
    node.setAttribute("role", "status");
    const heading = document.createElement("h3");
    heading.textContent = title;
    const summary = document.createElement("p");
    summary.textContent = plan.summary
        ? "Active filters: " + plan.summary + "."
        : "Nothing else is narrowing this list.";
    const actions = document.createElement("div");
    actions.className = "empty-actions";
    (plan.buttons || []).forEach(item => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = item.action === "clear" ? "text-btn empty-clear" : "text-btn empty-remove";
        button.textContent = item.label;
        if (item.action === "clear") button.addEventListener("click", clearFilters);
        else {
            button.addEventListener("click", () => {
                const entry = (entries || []).find(candidate => candidate.key === item.key);
                if (entry) entry.clear();
            });
        }
        actions.appendChild(button);
    });
    node.append(heading, summary, actions);
}

function paintEmptyState() {
    const entries = collectFilterActions();
    const order = rememberFilterOrder(entries);
    const section = document.getElementById("dealsSection");
    const emptyDeals = document.getElementById("emptyState");
    if (emptyDeals) {
        if (visibleDealCount() === 0) {
            const revealed = {};
            entries.forEach(entry => { revealed[entry.key] = revealCount(entry, "deals"); });
            const title = entries.length ? "No deals match these filters" : "No deals in this scan";
            fillEmpty(emptyDeals, emptyResetPlan(entries, revealed, order), entries, title);
            if (section) section.classList.add("is-empty");
        } else {
            emptyDeals.hidden = true;
            emptyDeals.replaceChildren();
            if (section) section.classList.remove("is-empty");
        }
    }
    const gone = document.getElementById("goneEmpty");
    if (!gone) return;
    const rows = goneRows();
    let shown = 0;
    rows.forEach(row => { if (goneRowMatches(row)) shown += 1; });
    if (rows.length && shown === 0 && entries.length) {
        const revealed = {};
        entries.forEach(entry => { revealed[entry.key] = revealCount(entry, "gone"); });
        fillEmpty(gone, emptyResetPlan(entries, revealed, order), entries, "No disappeared deals match these filters");
    } else {
        gone.hidden = true;
        gone.replaceChildren();
    }
}

function paintActiveChips() {
    const host = document.getElementById("activeChips");
    if (!host) return;
    const chips = collectFilterActions().filter(entry => entry.chip);
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
    // The last-update timestamp is public; scraper health stays internal.
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
    return text + "% vs list";
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
    if (Number.isFinite(list) && list > 0) rows.push({ label: "List price", value: quickMoney(symbol, list) });
    const percent = quickPercent(dataset.discount);
    if (percent) rows.push({ label: "Claimed discount", value: percent });
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
        if (offer.cheapest) label += " · cheapest listed";
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
        badge.title = "Store's claimed discount versus its list price. Not compared with tracked prices.";
        price.appendChild(badge);
    }
    identity.append(store, heading, price);
    appendQuickKeyFacts(identity, card.dataset, facts);
    const historyText = quickHistoryNote(facts);
    if (historyText) {
        const history = document.createElement("p");
        history.className = "quick-history";
        history.textContent = historyText;
        identity.appendChild(history);
    }
    const alsoText = quickAlsoLine(item);
    if (alsoText) {
        const also = document.createElement("p");
        also.className = "quick-also";
        also.textContent = alsoText;
        identity.appendChild(also);
    }
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

function quickHistoryNote(facts) {
    facts = facts || {};
    const points = facts.points || [];
    const symbol = facts.symbol || "$";
    if (!points.length) return "No tracked price history yet.";
    const only = points[0];
    if (points.length === 1) {
        const price = quickMoney(symbol, only[1]);
        const when = typeof quickShortDate === "function" ? quickShortDate(only[0]) : "";
        const shown = price ? " (" + price + (when ? " on " + when : "") + ")" : "";
        return "Only one tracked price" + shown + ". Not enough history to compare.";
    }
    const bits = [];
    const low = facts.atl && Number.isFinite(Number(facts.atl.price)) ? facts.atl : null;
    if (low) {
        const when = typeof quickShortDate === "function" ? quickShortDate(low.date) : "";
        bits.push("Tracked low " + quickMoney(symbol, low.price) + (when ? " on " + when : ""));
    }
    const last = points[points.length - 1];
    let prior = null;
    for (let i = points.length - 2; i >= 0; i--) {
        if (Math.abs(Number(points[i][1]) - Number(last[1])) > 0.001) {
            prior = points[i];
            break;
        }
    }
    const priorIsLow = !!(prior && low
        && String(prior[0]).slice(0, 10) === String(low.date || "").slice(0, 10)
        && Math.abs(Number(prior[1]) - Number(low.price)) < 0.001);
    if (prior && !priorIsLow) {
        const when = typeof quickShortDate === "function" ? quickShortDate(prior[0]) : "";
        bits.push("Previous tracked price " + quickMoney(symbol, prior[1]) + (when ? " on " + when : ""));
    }
    bits.push(points.length + " tracked prices");
    return bits.join(" · ") + ".";
}

function quickAlsoLine(item) {
    const offers = ((item && item.offers) || []).filter(offer => offer && offer.url && offer.url !== item.url);
    if (!offers.length) return "";
    const own = ((item && item.offers) || []).find(offer => offer && offer.url === item.url);
    const ownPrice = own ? Number(own.price) : NaN;
    return offers.map(offer => {
        const symbol = String(offer.currency || "USD").toUpperCase() === "EUR" ? "€" : "$";
        const price = Number(offer.price);
        const money = Number.isFinite(price) ? quickMoney(symbol, price) : "";
        const name = offer.store || "Store";
        const cheaper = Number.isFinite(ownPrice) && Number.isFinite(price) && price + 0.001 < ownPrice;
        const label = (cheaper ? "Cheaper at " : "Also at ") + name;
        return money ? label + " " + money : label;
    }).join(" · ");
}

function appendQuickKeyFacts(parent, dataset, facts) {
    dataset = dataset || {};
    facts = facts || {};
    const symbol = facts.symbol || "$";
    const bits = [];
    const list = Number(dataset.original);
    if (Number.isFinite(list) && list > 0) {
        bits.push({
            label: "List price",
            value: quickMoney(symbol, list),
            original: true,
            title: "Store's list price. The percent beside the sale price is this store's claimed discount, not a tracked market price."
        });
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
        if (bit.title) item.title = bit.title;
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
    const priceNote = document.createElement("p");
    priceNote.className = "quick-price-note";
    priceNote.textContent = "List price is the store's claimed original, not a tracked market price. Average and lowest use prices tracked here.";
    more.appendChild(priceNote);
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
    const samples = ((facts && facts.points) || []).length;
    const averageHint = !Number.isFinite(average)
        ? "No tracked prices in the last 90 days"
        : samples < 2
            ? "Only one tracked price in the last 90 days, so this is that price"
            : "Mean of tracked sale prices in the last 90 days";
    return [
        { label: "Now", value: Number.isFinite(now) ? quickMoney(symbol, now) : "—", hint: "Current sale price" },
        {
            label: "List price",
            value: Number.isFinite(list) && list > 0 ? quickMoney(symbol, list) : "—",
            hint: "Store list price, not a tracked market price",
            original: Number.isFinite(list) && list > 0
        },
        {
            label: "Average",
            value: Number.isFinite(average) ? quickMoney(symbol, average) : "No history",
            hint: averageHint
        },
        {
            label: "Lowest",
            value: Number.isFinite(low) ? quickMoney(symbol, low) : "No history",
            hint: Number.isFinite(low) ? "Lowest price tracked for this listing" : "No tracked low yet"
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
        meta.textContent = row.availability + (row.cheapest ? " · cheapest listed" : "");
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
    forgetLastVisit();
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
   Email alerts for the static page.
   The API is docs/alerts-api.md on the alerts backend (PR #60).
   This file has no API secrets. Tokens stay in the fragment, then leave it. */

const ALERTS_API_BASE = "";
const ALERTS_CONSENT_VERSION = "2026-10";
const ALERTS_SESSION_KEY = "skatedeals.alerts.manage";
const ALERTS_PARTS = ["Decks", "Wheels", "Trucks", "Bearings"];
const ALERTS_RULE_FIELDS = [
    "brand", "name", "part", "width", "min_width", "max_width", "back_in_stock_width",
    "max_price", "alert_on_drop", "alert_on_low", "alert_on_stock", "note"
];
const ALERTS_NUMBER_FIELDS = ["width", "min_width", "max_width", "back_in_stock_width", "max_price"];
const ALERTS_FLAG_FIELDS = ["alert_on_drop", "alert_on_low", "alert_on_stock"];
const ALERTS_ERRORS = {
    invalid_email: "That email address is not valid.",
    consent_required: "Check the box to agree before subscribing.",
    consent_outdated: "This page is out of date. Refresh and try again.",
    captcha_failed: "The captcha check failed. Try again.",
    invalid_rules: "Those alert details were rejected.",
    staging_recipient_not_allowed: "That address is not allowed on this server.",
    json_required: "The request was not accepted.",
    rate_limited: "Too many attempts. Nothing was changed.",
    signups_closed: "New signups are closed right now.",
    email_unavailable: "Email is unavailable right now.",
    service_unavailable: "Alerts are unavailable right now.",
    invalid_token: "That link is invalid or already used.",
    unavailable: "Email alerts coming soon.",
    body_too_large: "That request is too large.",
    origin_not_allowed: "This page is not allowed to call the alerts service.",
    internal_error: "Alerts are unavailable right now."
};

const alertsUi = {
    wired: false,
    open: false,
    config: null,
    client: null,
    view: "signup",
    entry: "digest",
    trigger: "below",
    broad: false,
    draft: null,
    editingId: "",
    prefs: null,
    token: "",
    active: false,
    busy: false,
    message: "",
    error: "",
    email: "",
    consent: false,
    health: null,
    confirm: "",
    returnFocus: null
};

function alertsResolveConfig(env) {
    env = env || {};
    const cfg = env.config || {};
    const host = String(env.host || "");
    const production = /(^|\.)github\.io$/i.test(host);
    const requested = String(cfg.apiBase || cfg.baseUrl || env.metaContent || env.fallbackBase || "").trim();
    const consentVersion = String(cfg.consentVersion || ALERTS_CONSENT_VERSION);
    const turnstileSiteKey = String(cfg.turnstileSiteKey || "").trim();
    if (requested && alertsBaseAllowed(requested, production)) {
        return {
            mode: "live",
            apiBase: alertsNormalizeBase(requested),
            consentVersion: consentVersion,
            turnstileSiteKey: turnstileSiteKey,
            production: production
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
    return null;
}

function consumeAlertsFragment() {
    if (typeof location === "undefined") return null;
    const parsed = readAlertsFragment(location.hash || "");
    if (!parsed || typeof history === "undefined" || !history.replaceState) return parsed;
    history.replaceState(null, "", (location.pathname || "/") + (location.search || ""));
    return parsed;
}

function manageTokenFromVerify(body) {
    body = body || {};
    if (body.manage_token) return String(body.manage_token);
    const link = String(body.manage_link || body.manage_url || "");
    const hash = link.indexOf("#") >= 0 ? link.slice(link.indexOf("#") + 1) : "";
    if (!hash) return "";
    const parsed = readAlertsFragment(hash);
    return parsed && parsed.purpose === "manage" ? parsed.token : "";
}

function alertsStorage() {
    try {
        if (typeof sessionStorage === "undefined" || !sessionStorage) return null;
        return sessionStorage;
    } catch (err) {
        return null;
    }
}

function readManageToken() {
    if (alertsUi.token) return alertsUi.token;
    const store = alertsStorage();
    if (!store) return "";
    try {
        return store.getItem(ALERTS_SESSION_KEY) || "";
    } catch (err) {
        return "";
    }
}

function storeManageToken(token) {
    alertsUi.token = token || "";
    const store = alertsStorage();
    if (!store || !token) return;
    try {
        store.setItem(ALERTS_SESSION_KEY, token);
    } catch (err) {
        /* the in-memory copy still works for this page view */
    }
}

function clearManageToken() {
    alertsUi.token = "";
    const store = alertsStorage();
    if (!store) return;
    try {
        store.removeItem(ALERTS_SESSION_KEY);
    } catch (err) {
        /* nothing else holds the token */
    }
}

function validEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email || "").trim());
}

function normalizeEmail(email) {
    return String(email || "").trim().toLowerCase();
}

function cleanText(value, max) {
    let text = String(value == null ? "" : value);
    if (text.normalize) text = text.normalize("NFKC");
    text = text.replace(/\s+/g, " ").trim();
    if (!text) return { ok: true, value: "" };
    if (/[\u0000-\u001f\u007f<>]/.test(text)) return { ok: false, error: "Remove <, >, and line breaks." };
    if (text.length > max) return { ok: false, error: "Keep that text to " + max + " characters." };
    return { ok: true, value: text };
}

function finiteNumber(value) {
    if (typeof value === "number") return Number.isFinite(value) ? value : null;
    const text = String(value == null ? "" : value).replace(/[$,]/g, "").trim();
    if (!text || !/^-?\d+(\.\d+)?$/.test(text)) return null;
    const num = Number(text);
    return Number.isFinite(num) ? num : null;
}

function deckWidth(value) {
    const num = finiteNumber(value);
    if (num == null || num < 5 || num > 12) return null;
    return num;
}

function cleanRule(rule) {
    const out = {};
    const source = rule || {};
    ALERTS_RULE_FIELDS.forEach(key => {
        if (source[key] == null || source[key] === "") return;
        if (ALERTS_FLAG_FIELDS.indexOf(key) >= 0) {
            if (source[key] === true) out[key] = true;
            return;
        }
        if (ALERTS_NUMBER_FIELDS.indexOf(key) >= 0) {
            if (typeof source[key] === "number" && Number.isFinite(source[key])) out[key] = source[key];
            return;
        }
        if (key === "part") {
            if (ALERTS_PARTS.indexOf(source[key]) >= 0) out[key] = source[key];
            return;
        }
        out[key] = source[key];
    });
    return out;
}

function buildRule(draft) {
    draft = draft || {};
    const brand = cleanText(draft.brand, 60);
    if (!brand.ok) return { ok: false, error: brand.error };
    const name = cleanText(draft.name, 80);
    if (!name.ok) return { ok: false, error: name.error };
    const note = cleanText(draft.note, 80);
    if (!note.ok) return { ok: false, error: note.error };
    if (!brand.value && !name.value) return { ok: false, error: "Enter a brand or a product name." };
    const part = ALERTS_PARTS.indexOf(draft.part) >= 0 ? draft.part : "";
    if (!part) return { ok: false, error: "Choose Decks, Wheels, Trucks, or Bearings." };
    const rule = { part: part };
    if (brand.value) rule.brand = brand.value;
    if (name.value) rule.name = name.value;
    if (part === "Decks" && draft.width != null && String(draft.width).trim() !== "") {
        const width = deckWidth(draft.width);
        if (width == null) return { ok: false, error: "Deck width must be a number from 5 to 12." };
        rule.width = width;
    }
    if (draft.max_price != null && String(draft.max_price).trim() !== "") {
        const price = finiteNumber(draft.max_price);
        if (price == null || price <= 0 || price > 2000) return { ok: false, error: "Max price must be greater than 0 and at most 2000." };
        rule.max_price = price;
    }
    if (draft.alert_on_drop === true) rule.alert_on_drop = true;
    if (draft.alert_on_low === true) rule.alert_on_low = true;
    if (draft.alert_on_stock === true) {
        rule.alert_on_stock = true;
        if (rule.width != null) rule.back_in_stock_width = rule.width;
    }
    if (note.value) rule.note = note.value;
    return { ok: true, rule: rule };
}

function ruleFromDraft(draft) {
    const built = buildRule(draft || {});
    return built.ok ? built.rule : {};
}

function blankAlertDraft() {
    return {
        kind: "digest",
        brand: "",
        name: "",
        part: "",
        width: "",
        price: "",
        max_price: "",
        alert_on_drop: false,
        alert_on_low: false,
        alert_on_stock: false,
        note: "",
        store: "",
        image: "",
        shoesize: ""
    };
}

function alertDraftFromDataset(dataset) {
    dataset = dataset || {};
    const part = ALERTS_PARTS.indexOf(dataset.part) >= 0 ? dataset.part : "";
    const width = part === "Decks" ? deckWidth(dataset.size) : null;
    let price = finiteNumber(dataset.price);
    if (price == null || price <= 0 || price > 2000) price = null;
    const shown = price == null ? "" : String(price);
    return {
        kind: "product",
        brand: dataset.brand || "",
        name: dataset.name || "",
        part: part,
        width: width == null ? "" : String(width),
        price: shown,
        max_price: shown,
        alert_on_drop: false,
        alert_on_low: false,
        alert_on_stock: false,
        note: "",
        store: dataset.store || "",
        image: "",
        shoesize: dataset.shoesize || ""
    };
}

function alertsEntryFromDraft(draft) {
    return draft && draft.kind === "product" ? "product" : "digest";
}

function alertsMoney(value) {
    const num = finiteNumber(value);
    if (num == null) return "";
    return "$" + num.toFixed(2);
}

// API v1 stores a brand or product-name rule only. A general deal list and an
// exact product watch are not fields the Worker accepts, so those actions never
// call subscribe and never report success.
function buildProductRule(draft, trigger) {
    const shaped = Object.assign({}, draft || {});
    shaped.note = "";
    if (trigger === "drop") {
        shaped.alert_on_drop = true;
        shaped.max_price = "";
    } else if (trigger === "below") {
        shaped.alert_on_drop = false;
        if (String(shaped.max_price == null ? "" : shaped.max_price).trim() === "") {
            return { ok: false, error: "Enter a price greater than 0 and at most 2000." };
        }
    } else {
        return { ok: false, error: "Choose a price or a meaningful drop." };
    }
    return buildRule(shaped);
}

function draftFromRule(rule) {
    rule = rule || {};
    return {
        brand: rule.brand || "",
        name: rule.name || "",
        part: rule.part || "",
        width: rule.width == null ? "" : String(rule.width),
        max_price: rule.max_price == null ? "" : String(rule.max_price),
        alert_on_drop: rule.alert_on_drop === true,
        alert_on_low: rule.alert_on_low === true,
        alert_on_stock: rule.alert_on_stock === true,
        note: rule.note || "",
        store: ""
    };
}

function alertsFailureMessage(result) {
    result = result || {};
    const body = result.body || {};
    const code = result.error || body.error || "";
    if (result.status === 503 || code === "service_unavailable" || body.ok === false) return "Alerts are unavailable right now.";
    let text = ALERTS_ERRORS[code] || "Something went wrong. Nothing was changed.";
    if (code === "rate_limited") {
        const wait = result.retryAfter || body.retry_after;
        text = "Too many attempts. Nothing was changed.";
        if (wait) text += " Retry after " + wait + " seconds.";
    }
    if (code === "captcha_failed" && alertsUi.health && alertsUi.health.mode !== "mock" && !(alertsUi.config && alertsUi.config.turnstileSiteKey)) {
        text = "The captcha check failed. This page has no Turnstile site key.";
    }
    const fields = body.fields;
    if (fields && typeof fields === "object") {
        const extra = Object.keys(fields).map(key => key + " (" + fields[key] + ")").join(", ");
        if (extra) text += " " + extra;
    }
    return text;
}

function alertsApplyResult(state, kind, result) {
    state = state || {};
    result = result || {};
    const body = result.body || {};
    state.error = "";
    if (kind === "health") {
        if (result.status === 200 && body.ok === true) {
            state.health = body;
            state.mockApi = body.mode === "mock";
            return state;
        }
        state.view = "down";
        state.active = false;
        state.health = null;
        state.error = "Alerts are unavailable right now.";
        return state;
    }
    if ((kind === "subscribe" || kind === "link") && result.status === 202 && body.status === "check_email") {
        state.view = "check";
        state.active = false;
        state.prefs = null;
        state.message = "Check your email to confirm.";
        return state;
    }
    if (kind === "verify" && result.status === 200 && body.status === "active" && body.manage_token && body.preferences && body.preferences.status === "active") {
        state.view = "manage";
        state.active = true;
        state.token = String(body.manage_token);
        state.prefs = body.preferences;
        state.message = "";
        return state;
    }
    if (kind === "preferences" && result.status === 200 && body.status === "active" && Array.isArray(body.rules)) {
        state.view = "manage";
        state.active = true;
        state.prefs = body;
        state.message = "";
        return state;
    }
    if (kind === "unsubscribe" && result.status === 200 && body.status === "unsubscribed") {
        state.view = "done";
        state.active = false;
        state.token = "";
        state.prefs = null;
        state.message = "You are unsubscribed. No alerts will be sent.";
        return state;
    }
    if (kind === "delete" && result.status === 200 && body.status === "deleted") {
        state.view = "done";
        state.active = false;
        state.token = "";
        state.prefs = null;
        state.message = "Your alerts data was deleted.";
        return state;
    }
    state.active = false;
    state.error = alertsFailureMessage(result);
    if (body.error === "invalid_token" || result.status === 401) {
        state.view = "relink";
        state.token = "";
        state.prefs = null;
    } else if (result.status === 503 || body.error === "service_unavailable" || body.ok === false) {
        state.view = "down";
    }
    return state;
}

function createAlertsClient(config, fetchImpl) {
    const fetchFn = fetchImpl || (typeof fetch === "function" ? fetch : null);
    const live = !!(config && config.mode === "live" && config.apiBase);

    async function request(method, path, options) {
        options = options || {};
        if (!live || !fetchFn) return { ok: false, status: 0, error: "unavailable", body: null };
        const headers = { Accept: "application/json" };
        let body;
        if (options.body != null) {
            headers["Content-Type"] = "application/json";
            body = JSON.stringify(options.body);
            if (body.length > 16 * 1024) return { ok: false, status: 413, error: "body_too_large", body: { error: "body_too_large" } };
        }
        if (options.token) headers.Authorization = "Bearer " + options.token;
        let response;
        try {
            response = await fetchFn(config.apiBase + path, {
                method: method,
                credentials: "omit",
                headers: headers,
                body: body
            });
        } catch (err) {
            return { ok: false, status: 0, error: "network", body: null };
        }
        let payload = null;
        if (response && typeof response.json === "function") {
            try {
                payload = await response.json();
            } catch (err) {
                payload = null;
            }
        }
        let retry = "";
        if (response && response.headers && typeof response.headers.get === "function") retry = response.headers.get("Retry-After") || "";
        return {
            ok: !!(response && response.ok),
            status: response ? response.status : 0,
            body: payload,
            error: payload && payload.error,
            retryAfter: (payload && payload.retry_after) || retry || ""
        };
    }

    return {
        health() { return request("GET", "/v1/health"); },
        subscribe(payload) { return request("POST", "/v1/subscribe", { body: payload }); },
        verify(token) { return request("POST", "/v1/verify", { body: { token: token } }); },
        link(payload) { return request("POST", "/v1/link", { body: payload }); },
        getPreferences(token) { return request("GET", "/v1/preferences", { token: token }); },
        putPreferences(token, rules) {
            return request("PUT", "/v1/preferences", { token: token, body: { rules: (rules || []).map(cleanRule) } });
        },
        unsubscribe(token) { return request("POST", "/v1/unsubscribe", { token: token }); },
        deleteSubscriber(token) { return request("DELETE", "/v1/subscriber", { token: token }); }
    };
}

function alertsEl(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
}

function setHidden(node, hidden) {
    if (!node) return;
    node.hidden = !!hidden;
    if (hidden) node.setAttribute("hidden", "");
    else node.removeAttribute("hidden");
}

function ruleTitle(rule) {
    const bits = [];
    if (rule.brand) bits.push(rule.brand);
    if (rule.name) bits.push(rule.name);
    return bits.join(" · ") || "Alert";
}

function ruleDetail(rule) {
    const bits = [];
    if (rule.part) bits.push(rule.part);
    if (rule.width != null) bits.push(rule.width + "\"");
    if (rule.min_width != null || rule.max_width != null) bits.push((rule.min_width || "any") + "–" + (rule.max_width || "any"));
    if (rule.max_price != null) bits.push("under $" + rule.max_price);
    if (rule.alert_on_drop) bits.push("Meaningful drop");
    if (rule.alert_on_low) bits.push("Historical low");
    if (rule.alert_on_stock) bits.push("Verified restock");
    if (!rule.alert_on_drop && !rule.alert_on_low && !rule.alert_on_stock) bits.push("Default: first match, then a drop or restock");
    if (rule.note) bits.push(rule.note);
    return bits.join(" · ");
}

function fieldWrap(id, label, control) {
    const wrap = alertsEl("label", "alerts-field");
    wrap.append(alertsEl("span", "", label), control);
    control.id = id;
    return wrap;
}

function checkWrap(id, label, checked) {
    const wrap = alertsEl("label", "alerts-check");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = id;
    input.checked = !!checked;
    wrap.append(input, alertsEl("span", "", label));
    return wrap;
}

function buttonEl(label, className, action, ruleId) {
    const button = alertsEl("button", className, label);
    button.type = "button";
    button.setAttribute("data-action", action);
    if (ruleId) button.setAttribute("data-rule-id", ruleId);
    return button;
}

function inputEl(type, value) {
    const input = document.createElement("input");
    input.type = type;
    input.value = value == null ? "" : String(value);
    return input;
}

function paintRuleFields(parent, draft) {
    const brand = inputEl("text", draft.brand);
    brand.maxLength = 60;
    brand.autocomplete = "off";
    parent.appendChild(fieldWrap("alertsBrand", "Brand", brand));
    const name = inputEl("text", draft.name);
    name.maxLength = 80;
    parent.appendChild(fieldWrap("alertsName", "Product name", name));
    const part = document.createElement("select");
    [["", "Choose a part"], ["Decks", "Decks"], ["Wheels", "Wheels"], ["Trucks", "Trucks"], ["Bearings", "Bearings"]].forEach(pair => {
        const option = alertsEl("option", "", pair[1]);
        option.value = pair[0];
        part.appendChild(option);
    });
    part.value = draft.part || "";
    parent.appendChild(fieldWrap("alertsPart", "Part", part));
    const width = inputEl("text", draft.width);
    width.inputMode = "decimal";
    parent.appendChild(fieldWrap("alertsWidth", "Deck width (5–12, optional)", width));
    const price = inputEl("text", draft.max_price);
    price.inputMode = "decimal";
    parent.appendChild(fieldWrap("alertsPrice", "Max price (optional)", price));
    const triggers = alertsEl("fieldset", "alerts-triggers");
    triggers.appendChild(alertsEl("legend", "alerts-legend", "Only alert on"));
    triggers.appendChild(checkWrap("alertsDrop", "Meaningful drop", draft.alert_on_drop));
    triggers.appendChild(checkWrap("alertsLow", "Historical low", draft.alert_on_low));
    triggers.appendChild(checkWrap("alertsStock", "Verified restock", draft.alert_on_stock));
    parent.appendChild(triggers);
    parent.appendChild(alertsEl("p", "alerts-hint", "Leave these off to be alerted once when a listing first matches, then on a meaningful drop or a verified restock."));
    const note = inputEl("text", draft.note);
    note.maxLength = 80;
    parent.appendChild(fieldWrap("alertsNote", "Note (optional)", note));
}

function draftFromForm(base) {
    const draft = Object.assign({}, base || blankAlertDraft());
    const value = id => {
        const node = document.getElementById(id);
        return node ? node.value : "";
    };
    const checked = id => {
        const node = document.getElementById(id);
        return !!(node && node.checked);
    };
    if (document.getElementById("alertsBrand")) {
        draft.brand = value("alertsBrand");
        draft.name = value("alertsName");
        draft.part = value("alertsPart");
        draft.width = value("alertsWidth");
        draft.max_price = value("alertsPrice");
        draft.note = value("alertsNote");
        draft.alert_on_drop = checked("alertsDrop");
        draft.alert_on_low = checked("alertsLow");
        draft.alert_on_stock = checked("alertsStock");
    }
    return draft;
}

function turnstileToken() {
    if (alertsUi.health && alertsUi.health.mode === "mock") return "mock-turnstile-pass";
    if (typeof turnstile !== "undefined" && turnstile && typeof turnstile.getResponse === "function") {
        return turnstile.getResponse() || "";
    }
    return "";
}

function ensureTurnstile(parent) {
    const key = alertsUi.config && alertsUi.config.turnstileSiteKey;
    if (!key || (alertsUi.health && alertsUi.health.mode === "mock")) return;
    const slot = alertsEl("div", "alerts-turnstile");
    slot.setAttribute("data-sitekey", key);
    parent.appendChild(slot);
    if (document.getElementById("alertsTurnstileScript")) return;
    const script = document.createElement("script");
    script.id = "alertsTurnstileScript";
    script.async = true;
    script.defer = true;
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
    if (document.body) document.body.appendChild(script);
}

function paintSoon(body) {
    body.appendChild(alertsEl("p", "alerts-copy", "Email alerts coming soon."));
    body.appendChild(alertsEl("p", "alerts-copy", "Nothing here subscribes you."));
    body.appendChild(alertsEl("p", "alerts-hint", "You'd be able to watch a brand, a deck, or a price from the cards on this page."));
}

function paintDown(body) {
    body.appendChild(alertsEl("p", "alerts-copy", "Alerts are unavailable right now."));
}

function paintCheck(body) {
    body.appendChild(alertsEl("p", "alerts-copy", alertsUi.message || "Check your email to confirm."));
    body.appendChild(alertsEl("p", "alerts-hint", "If this address is already active, that email is a manage link and these rules were not saved."));
    if (alertsUi.entry === "product") {
        body.appendChild(alertsEl("p", "alerts-hint", "This watch matches listings by brand and name words. It is not limited to one product, and it is not active yet."));
    }
    const actions = alertsEl("div", "alerts-actions");
    actions.appendChild(buttonEl("Email me a link", "alerts-secondary", "relink"));
    actions.appendChild(buttonEl("Use a different address", "alerts-secondary", "reset-signup"));
    body.appendChild(actions);
}

function paintDone(body) {
    body.appendChild(alertsEl("p", "alerts-copy", alertsUi.message || "You are unsubscribed. No alerts will be sent."));
    body.appendChild(buttonEl("Create an alert", "alerts-secondary", "reset-signup"));
}

function paintVerifyNote(parent) {
    parent.appendChild(alertsEl("p", "alerts-verify", "We'll email you a link to confirm. Nothing is active until you verify that link."));
}

function paintAdvancedShell() {
    const advanced = document.createElement("details");
    advanced.className = "alerts-advanced";
    advanced.id = "alertsAdvanced";
    advanced.open = false;
    const summary = document.createElement("summary");
    summary.textContent = "Advanced options";
    advanced.appendChild(summary);
    return advanced;
}

function paintDigestAdvanced(parent) {
    const advanced = paintAdvancedShell();
    advanced.appendChild(alertsEl("p", "alerts-soon", "Notification preferences for this list are coming soon."));
    advanced.appendChild(alertsEl("p", "alerts-hint", "New deals, price drops, and historical lows on the general list are not available yet. The service can store those switches only on a brand or product-name rule, which is a different alert."));
    parent.appendChild(advanced);
}

function paintDigestSignup(body) {
    if (alertsUi.health && alertsUi.health.mode === "mock") {
        body.appendChild(alertsEl("p", "alerts-banner", "This is a local mock. No email is sent."));
    } else if (alertsUi.healthUnread) {
        body.appendChild(alertsEl("p", "alerts-banner", "The alerts status check could not be read from this page."));
    }
    body.appendChild(alertsEl("p", "alerts-copy", "Get general SkateDeals deal emails. This is not a watch on one product."));
    body.appendChild(alertsEl("p", "alerts-soon", "General deal emails are coming soon. Nothing was subscribed."));
    const form = alertsEl("form", "alerts-form");
    form.id = "alertsForm";
    form.noValidate = true;
    form.addEventListener("submit", submitSignup);
    const email = inputEl("email", alertsUi.email);
    email.autocomplete = "email";
    email.required = true;
    email.setAttribute("aria-required", "true");
    form.appendChild(fieldWrap("alertsEmail", "Email", email));
    form.appendChild(checkWrap("alertsConsent", "I agree to receive SkateDeals deal emails. I can unsubscribe at any time.", alertsUi.consent));
    const actions = alertsEl("div", "alerts-actions");
    const submit = alertsEl("button", "alerts-primary", "Subscribe");
    submit.id = "alertsSubmit";
    submit.type = "submit";
    actions.appendChild(submit);
    if (readManageToken()) actions.appendChild(buttonEl("Manage alerts", "alerts-secondary", "manage-saved"));
    actions.appendChild(buttonEl("I already confirmed", "alerts-secondary", "relink"));
    form.appendChild(actions);
    paintVerifyNote(form);
    paintDigestAdvanced(form);
    body.appendChild(form);
}

function alertsProductImage(card) {
    if (!card || typeof card.querySelector !== "function") return "";
    const img = card.querySelector("img");
    if (!img) return "";
    const src = img.getAttribute ? (img.getAttribute("src") || "") : "";
    return /^https?:\/\//i.test(src) ? src : "";
}

function paintProductSummary(body, draft) {
    const row = alertsEl("div", "alerts-product");
    const src = String(draft.image || "");
    if (/^https?:\/\//i.test(src)) {
        const img = document.createElement("img");
        img.className = "alerts-product-photo";
        img.alt = draft.name || "Product photo";
        img.src = src;
        img.setAttribute("src", src);
        img.addEventListener("error", () => { img.hidden = true; });
        row.appendChild(img);
    }
    const text = alertsEl("div", "alerts-product-copy");
    text.appendChild(alertsEl("p", "alerts-product-name", draft.name || "This product"));
    const price = alertsMoney(draft.price);
    text.appendChild(alertsEl("p", "alerts-product-price", price ? "Current price " + price : "Current price unavailable"));
    row.appendChild(text);
    body.appendChild(row);
}

function setAlertsEnabled(ids, enabled) {
    ids.forEach(id => {
        const node = document.getElementById(id);
        if (node) node.disabled = !enabled;
    });
}

function paintProductAdvanced(form, draft) {
    const advanced = paintAdvancedShell();
    advanced.appendChild(alertsEl("p", "alerts-section", "Matching"));
    advanced.appendChild(alertsEl("p", "alerts-soon", "Watching this exact product is coming soon. The service cannot store a product link or a single product id."));
    advanced.appendChild(checkWrap("alertsBroad", "Match listings by brand and name (other products can match).", alertsUi.broad));
    advanced.appendChild(alertsEl("p", "alerts-hint", "Leave this off to avoid a broader watch. Every word of the brand must appear in the listing name. The product name is matched as words, not as this exact item."));
    const brand = inputEl("text", draft.brand);
    brand.maxLength = 60;
    brand.autocomplete = "off";
    brand.disabled = !alertsUi.broad;
    advanced.appendChild(fieldWrap("alertsBrand", "Brand", brand));
    const name = inputEl("text", draft.name);
    name.maxLength = 80;
    name.disabled = !alertsUi.broad;
    advanced.appendChild(fieldWrap("alertsName", "Product name", name));
    const part = document.createElement("select");
    part.disabled = !alertsUi.broad;
    [["", "Choose a part"], ["Decks", "Decks"], ["Wheels", "Wheels"], ["Trucks", "Trucks"], ["Bearings", "Bearings"]].forEach(pair => {
        const option = alertsEl("option", "", pair[1]);
        option.value = pair[0];
        part.appendChild(option);
    });
    part.value = draft.part || "";
    advanced.appendChild(fieldWrap("alertsPart", "Part", part));
    advanced.appendChild(alertsEl("p", "alerts-section", "Sizes"));
    const width = inputEl("text", draft.width);
    width.inputMode = "decimal";
    width.disabled = !alertsUi.broad;
    width.setAttribute("aria-label", "Deck width from 5 to 12");
    advanced.appendChild(fieldWrap("alertsWidth", "Deck width (5–12)", width));
    advanced.appendChild(alertsEl("p", "alerts-hint", "Only a deck width is saved. Other sizes are coming soon and are not sent."));
    if (draft.shoesize) {
        advanced.appendChild(alertsEl("p", "alerts-soon", "Sizes on this product (" + draft.shoesize + ") are coming soon and are not sent."));
    }
    advanced.appendChild(alertsEl("p", "alerts-section", "Tracked lows"));
    const lowWrap = checkWrap("alertsLow", "Verified historical low", draft.alert_on_low);
    const lowInput = lowWrap.querySelector("input");
    if (lowInput) lowInput.disabled = !alertsUi.broad;
    advanced.appendChild(lowWrap);
    advanced.appendChild(alertsEl("p", "alerts-section", "Verified restock"));
    const stockWrap = checkWrap("alertsStock", "Verified restock", draft.alert_on_stock);
    const stockInput = stockWrap.querySelector("input");
    if (stockInput) stockInput.disabled = !alertsUi.broad;
    advanced.appendChild(stockWrap);
    advanced.appendChild(alertsEl("p", "alerts-hint", "For a deck, the width above is included as the restock width."));
    form.appendChild(advanced);
    const broadInput = advanced.querySelector("#alertsBroad");
    if (broadInput) {
        broadInput.addEventListener("change", () => {
            setAlertsEnabled(["alertsBrand", "alertsName", "alertsPart", "alertsWidth", "alertsLow", "alertsStock"], broadInput.checked);
        });
    }
}

function paintProductChoices(form, draft) {
    const group = alertsEl("fieldset", "alerts-choices");
    const legend = alertsEl("legend", "alerts-legend", "Notify me");
    group.appendChild(legend);
    const belowLabel = alertsEl("label", "alerts-choice");
    const below = document.createElement("input");
    below.type = "radio";
    below.name = "alertsTrigger";
    below.id = "alertsTriggerBelow";
    below.checked = alertsUi.trigger !== "drop";
    belowLabel.append(below, alertsEl("span", "", "Alert when below $"));
    const price = inputEl("text", draft.max_price);
    price.id = "alertsPrice";
    price.inputMode = "decimal";
    price.autocomplete = "off";
    price.setAttribute("aria-label", "Price threshold in dollars");
    belowLabel.appendChild(price);
    group.appendChild(belowLabel);
    const dropLabel = alertsEl("label", "alerts-choice");
    const drop = document.createElement("input");
    drop.type = "radio";
    drop.name = "alertsTrigger";
    drop.id = "alertsTriggerDrop";
    drop.checked = alertsUi.trigger === "drop";
    dropLabel.append(drop, alertsEl("span", "", "Any meaningful price drop"));
    group.appendChild(dropLabel);
    form.appendChild(group);
    price.addEventListener("focus", () => {
        below.checked = true;
        drop.checked = false;
    });
}

function paintProductSignup(body) {
    if (alertsUi.health && alertsUi.health.mode === "mock") {
        body.appendChild(alertsEl("p", "alerts-banner", "This is a local mock. No email is sent."));
    } else if (alertsUi.healthUnread) {
        body.appendChild(alertsEl("p", "alerts-banner", "The alerts status check could not be read from this page."));
    }
    const draft = alertsUi.draft || blankAlertDraft();
    paintProductSummary(body, draft);
    body.appendChild(alertsEl("p", "alerts-copy", "Email you about this product."));
    const form = alertsEl("form", "alerts-form");
    form.id = "alertsForm";
    form.noValidate = true;
    form.addEventListener("submit", submitSignup);
    paintProductChoices(form, draft);
    const email = inputEl("email", alertsUi.email);
    email.autocomplete = "email";
    email.required = true;
    email.setAttribute("aria-required", "true");
    form.appendChild(fieldWrap("alertsEmail", "Email", email));
    form.appendChild(checkWrap("alertsConsent", "I agree to receive email about this alert. I can unsubscribe at any time.", alertsUi.consent));
    ensureTurnstile(form);
    const actions = alertsEl("div", "alerts-actions");
    const submit = alertsEl("button", "alerts-primary", "Create alert");
    submit.id = "alertsSubmit";
    submit.type = "submit";
    actions.appendChild(submit);
    actions.appendChild(buttonEl("I already confirmed", "alerts-secondary", "relink"));
    form.appendChild(actions);
    paintVerifyNote(form);
    form.appendChild(alertsEl("p", "alerts-soon", "An exact watch of this product is coming soon."));
    paintProductAdvanced(form, draft);
    body.appendChild(form);
}

function paintUnsupported(body) {
    const status = alertsEl("p", "alerts-soon", alertsUi.entry === "product"
        ? "Watching this exact product is coming soon. Nothing was saved."
        : "General deal emails are coming soon. Nothing was subscribed.");
    status.setAttribute("role", "status");
    body.appendChild(status);
    body.appendChild(alertsEl("p", "alerts-copy", alertsUi.entry === "product"
        ? "No email was sent. Brand and name matching stayed off, so this was not saved as a broader watch."
        : "No email was sent."));
    const back = buttonEl("Back", "alerts-secondary", "reset-signup");
    back.id = "alertsBack";
    body.appendChild(back);
}

function paintSignup(body) {
    if (alertsUi.entry === "product") paintProductSignup(body);
    else paintDigestSignup(body);
}

function paintRelink(body) {
    if (alertsUi.health && alertsUi.health.mode === "mock") {
        body.appendChild(alertsEl("p", "alerts-banner", "This is a local mock. No email is sent."));
    }
    body.appendChild(alertsEl("p", "alerts-copy", "Email me a link"));
    const form = alertsEl("form", "alerts-form");
    form.id = "alertsLinkForm";
    form.noValidate = true;
    form.addEventListener("submit", submitLink);
    const email = inputEl("email", alertsUi.email);
    email.autocomplete = "email";
    form.appendChild(fieldWrap("alertsLinkEmail", "Email", email));
    ensureTurnstile(form);
    const actions = alertsEl("div", "alerts-actions");
    const submit = alertsEl("button", "alerts-primary", "Email me a link");
    submit.type = "submit";
    actions.appendChild(submit);
    actions.appendChild(buttonEl("Create an alert", "alerts-secondary", "reset-signup"));
    form.appendChild(actions);
    body.appendChild(form);
}

function paintManage(body) {
    const prefs = alertsUi.prefs || {};
    if (alertsUi.active && prefs.status === "active") {
        const badge = alertsEl("p", "alerts-status is-active", "Active");
        body.appendChild(badge);
    }
    const who = prefs.email_masked ? "Alerts for " + prefs.email_masked + "." : "Your confirmed alerts.";
    body.appendChild(alertsEl("p", "alerts-copy", who));
    const rules = prefs.rules || [];
    const max = prefs.max_rules || 10;
    rules.forEach(rule => {
        const card = alertsEl("article", "alerts-rule");
        card.appendChild(alertsEl("h3", "", ruleTitle(rule)));
        card.appendChild(alertsEl("p", "alerts-hint", ruleDetail(rule)));
        const actions = alertsEl("div", "alerts-actions");
        actions.appendChild(buttonEl("Edit", "alerts-secondary", "edit", rule.id || ""));
        actions.appendChild(buttonEl("Remove", "alerts-secondary", "remove", rule.id || ""));
        card.appendChild(actions);
        body.appendChild(card);
    });
    if (!rules.length) body.appendChild(alertsEl("p", "alerts-hint", "You have no alerts yet."));
    const actions = alertsEl("div", "alerts-actions");
    if (rules.length < max) actions.appendChild(buttonEl("Add alert", "alerts-primary", "add"));
    else actions.appendChild(alertsEl("p", "alerts-hint", "This account is at its " + max + " alert limit."));
    actions.appendChild(buttonEl("Unsubscribe", "alerts-danger", "unsubscribe"));
    actions.appendChild(buttonEl("Delete my data", "alerts-danger", "delete"));
    body.appendChild(actions);
    if (alertsUi.confirm === "unsubscribe" || alertsUi.confirm === "delete") {
        const note = alertsUi.confirm === "delete" ? "Delete the address and every alert?" : "Unsubscribe this address?";
        body.appendChild(alertsEl("p", "alerts-copy", note));
        const row = alertsEl("div", "alerts-actions");
        row.appendChild(buttonEl(alertsUi.confirm === "delete" ? "Delete" : "Confirm unsubscribe", "alerts-danger", "confirm-" + alertsUi.confirm));
        row.appendChild(buttonEl("Cancel", "alerts-secondary", "cancel-confirm"));
        body.appendChild(row);
    }
}

function paintEdit(body) {
    body.appendChild(alertsEl("p", "alerts-hint", "This matches listings by brand and name words. It is not a general deal email and not one exact product."));
    const draft = alertsUi.draft || blankAlertDraft();
    const form = alertsEl("form", "alerts-form");
    form.id = "alertsEditForm";
    form.noValidate = true;
    form.addEventListener("submit", submitEdit);
    paintRuleFields(form, draft);
    const actions = alertsEl("div", "alerts-actions");
    const submit = alertsEl("button", "alerts-primary", alertsUi.editingId ? "Save alert" : "Add alert");
    submit.id = "alertsSubmit";
    submit.type = "submit";
    actions.appendChild(submit);
    actions.appendChild(buttonEl("Cancel", "alerts-secondary", "cancel-edit"));
    form.appendChild(actions);
    body.appendChild(form);
}

function paintAlerts(focusId) {
    const title = document.getElementById("alertsTitle");
    const live = document.getElementById("alertsLive");
    const error = document.getElementById("alertsError");
    const body = document.getElementById("alertsBody");
    if (!body) return;
    const titles = {
        soon: "Alerts",
        down: "Alerts",
        signup: alertsUi.entry === "product" ? "Alert me" : "Subscribe",
        unsupported: alertsUi.entry === "product" ? "Alert me" : "Subscribe",
        check: "Check your email",
        manage: "Manage alerts",
        edit: alertsUi.editingId ? "Edit alert" : "Add alert",
        relink: "Email me a link",
        done: "Alerts"
    };
    if (title) title.textContent = titles[alertsUi.view] || "Alerts";
    if (live) live.textContent = (alertsUi.view === "check" || alertsUi.view === "unsupported") ? "" : (alertsUi.message || "");
    if (error) error.textContent = alertsUi.error || "";
    body.replaceChildren();
    if (alertsUi.view === "soon") paintSoon(body);
    else if (alertsUi.view === "down") paintDown(body);
    else if (alertsUi.view === "check") paintCheck(body);
    else if (alertsUi.view === "unsupported") paintUnsupported(body);
    else if (alertsUi.view === "done") paintDone(body);
    else if (alertsUi.view === "manage") paintManage(body);
    else if (alertsUi.view === "edit") paintEdit(body);
    else if (alertsUi.view === "relink") paintRelink(body);
    else paintSignup(body);
    const focus = document.getElementById(focusId || (alertsUi.view === "unsupported" ? "alertsBack" : ""));
    if (focus && focus.focus) focus.focus();
}

function adoptAlerts(state) {
    if (state.view) alertsUi.view = state.view;
    alertsUi.message = state.message || "";
    alertsUi.error = state.error || "";
    alertsUi.active = !!state.active;
    alertsUi.prefs = state.prefs || null;
    if (state.health) alertsUi.health = state.health;
    if (state.token) storeManageToken(state.token);
    if (state.active === false && (state.view === "relink" || state.view === "done" || state.view === "down" || state.view === "check")) {
        if (state.view !== "check") clearManageToken();
    }
}

async function refreshHealth() {
    alertsUi.health = null;
    alertsUi.healthUnread = false;
    const result = await alertsUi.client.health();
    if (!result || result.status === 0) {
        alertsUi.healthUnread = true;
        return;
    }
    const state = alertsApplyResult({}, "health", result);
    if (state.health) alertsUi.health = state.health;
    if (state.view === "down") adoptAlerts(state);
}

async function verifyAlertsToken(token) {
    alertsUi.busy = true;
    alertsUi.view = "check";
    alertsUi.message = "Confirming your email…";
    alertsUi.active = false;
    paintAlerts();
    const result = await alertsUi.client.verify(token);
    alertsUi.busy = false;
    adoptAlerts(alertsApplyResult({ active: false }, "verify", result));
    paintAlerts();
}

async function loadAlertsPreferences(token) {
    alertsUi.busy = true;
    const result = await alertsUi.client.getPreferences(token);
    alertsUi.busy = false;
    const state = alertsApplyResult({ active: false }, "preferences", result);
    if (state.active) state.token = token;
    adoptAlerts(state);
    paintAlerts();
}

function readProductTrigger() {
    const drop = document.getElementById("alertsTriggerDrop");
    const below = document.getElementById("alertsTriggerBelow");
    if (drop && drop.checked) return "drop";
    if (below && below.checked) return "below";
    return alertsUi.trigger === "drop" ? "drop" : "below";
}

async function submitSignup(event) {
    if (event && event.preventDefault) event.preventDefault();
    if (alertsUi.busy || !alertsUi.client) return;
    const emailNode = document.getElementById("alertsEmail");
    const consentNode = document.getElementById("alertsConsent");
    alertsUi.email = emailNode ? emailNode.value : "";
    alertsUi.consent = !!(consentNode && consentNode.checked);
    alertsUi.draft = draftFromForm(alertsUi.draft);
    alertsUi.active = false;
    if (alertsUi.entry === "product") {
        alertsUi.trigger = readProductTrigger();
        const broadNode = document.getElementById("alertsBroad");
        alertsUi.broad = !!(broadNode && broadNode.checked);
    }
    if (!validEmail(alertsUi.email)) {
        alertsUi.error = "Enter an email address. Nothing was saved.";
        paintAlerts("alertsEmail");
        return;
    }
    if (!alertsUi.consent) {
        alertsUi.error = "Check the box to agree before subscribing. Nothing was saved.";
        paintAlerts("alertsConsent");
        return;
    }
    if (alertsUi.entry !== "product") {
        alertsUi.error = "";
        alertsUi.message = "";
        alertsUi.view = "unsupported";
        paintAlerts();
        return;
    }
    if (!alertsUi.broad) {
        alertsUi.error = "";
        alertsUi.message = "";
        alertsUi.view = "unsupported";
        paintAlerts();
        return;
    }
    const built = buildProductRule(alertsUi.draft, alertsUi.trigger);
    if (!built.ok) {
        alertsUi.error = built.error + " Nothing was saved.";
        paintAlerts();
        return;
    }
    const token = turnstileToken();
    alertsUi.busy = true;
    alertsUi.error = "";
    const result = await alertsUi.client.subscribe({
        email: normalizeEmail(alertsUi.email),
        rules: [built.rule],
        consent: true,
        consent_version: alertsUi.config.consentVersion,
        turnstile_token: token
    });
    alertsUi.busy = false;
    adoptAlerts(alertsApplyResult({ active: false, view: "signup" }, "subscribe", result));
    if (alertsUi.view !== "check") alertsUi.view = alertsUi.view === "down" ? "down" : "signup";
    paintAlerts();
}

async function submitLink(event) {
    if (event && event.preventDefault) event.preventDefault();
    if (alertsUi.busy || !alertsUi.client) return;
    const emailNode = document.getElementById("alertsLinkEmail");
    alertsUi.email = emailNode ? emailNode.value : "";
    if (!validEmail(alertsUi.email)) {
        alertsUi.error = "Enter an email address.";
        paintAlerts("alertsLinkEmail");
        return;
    }
    if (!alertsUi.health) await refreshHealth();
    alertsUi.busy = true;
    const result = await alertsUi.client.link({
        email: normalizeEmail(alertsUi.email),
        turnstile_token: turnstileToken()
    });
    alertsUi.busy = false;
    adoptAlerts(alertsApplyResult({ active: false }, "link", result));
    paintAlerts();
}

function rulesAfterEdit(nextRule) {
    const current = (alertsUi.prefs && alertsUi.prefs.rules) || [];
    const rules = current.map(cleanRule);
    if (alertsUi.editingId) {
        const index = current.findIndex(rule => rule && rule.id === alertsUi.editingId);
        if (index >= 0) rules[index] = nextRule;
        else rules.push(nextRule);
    } else {
        rules.push(nextRule);
    }
    return rules;
}

async function submitEdit(event) {
    if (event && event.preventDefault) event.preventDefault();
    if (alertsUi.busy || !alertsUi.client) return;
    alertsUi.draft = draftFromForm(alertsUi.draft);
    const built = buildRule(alertsUi.draft);
    if (!built.ok) {
        alertsUi.error = built.error;
        paintAlerts();
        return;
    }
    const max = (alertsUi.prefs && alertsUi.prefs.max_rules) || 10;
    const rules = rulesAfterEdit(built.rule);
    const existing = (alertsUi.prefs && alertsUi.prefs.rules) || [];
    if (!alertsUi.editingId && existing.length >= max) {
        alertsUi.error = "This account is at its " + max + " alert limit.";
        paintAlerts();
        return;
    }
    const token = readManageToken();
    alertsUi.busy = true;
    const result = await alertsUi.client.putPreferences(token, rules);
    alertsUi.busy = false;
    const previous = alertsUi.view;
    const state = alertsApplyResult({ active: alertsUi.active, prefs: alertsUi.prefs, view: previous }, "preferences", result);
    if (!(result.status === 200 && result.body && result.body.status === "active")) {
        alertsUi.error = alertsFailureMessage(result);
        alertsUi.view = "edit";
        paintAlerts();
        return;
    }
    adoptAlerts(state);
    alertsUi.editingId = "";
    alertsUi.confirm = "";
    paintAlerts();
}

async function removeAlert(id) {
    const rules = (alertsUi.prefs && alertsUi.prefs.rules) || [];
    if (rules.length <= 1) {
        alertsUi.error = "Unsubscribe to remove the last alert.";
        alertsUi.view = "manage";
        paintAlerts();
        return;
    }
    const next = rules.filter(rule => rule.id !== id).map(cleanRule);
    const token = readManageToken();
    alertsUi.busy = true;
    const result = await alertsUi.client.putPreferences(token, next);
    alertsUi.busy = false;
    if (!(result.status === 200 && result.body && result.body.status === "active")) {
        alertsUi.error = alertsFailureMessage(result);
        alertsUi.view = "manage";
        paintAlerts();
        return;
    }
    adoptAlerts(alertsApplyResult({ active: false }, "preferences", result));
    paintAlerts();
}

async function finishSubscription(kind) {
    const token = readManageToken();
    alertsUi.busy = true;
    const result = kind === "delete" ? await alertsUi.client.deleteSubscriber(token) : await alertsUi.client.unsubscribe(token);
    alertsUi.busy = false;
    adoptAlerts(alertsApplyResult({ active: false }, kind, result));
    alertsUi.confirm = "";
    paintAlerts();
}

function onAlertsClick(event) {
    const target = event.target;
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
        alertsUi.active = false;
        paintAlerts("alertsLinkEmail");
    } else if (action === "reset-signup") {
        alertsUi.view = "signup";
        alertsUi.error = "";
        alertsUi.message = "";
        alertsUi.active = false;
        alertsUi.prefs = null;
        alertsUi.draft = alertsUi.draft || blankAlertDraft();
        alertsUi.entry = alertsEntryFromDraft(alertsUi.draft);
        paintAlerts("alertsEmail");
    } else if (action === "manage-saved") {
        const saved = readManageToken();
        alertsUi.error = "";
        alertsUi.message = "";
        alertsUi.active = false;
        if (!saved) {
            alertsUi.view = "relink";
            paintAlerts("alertsLinkEmail");
            return;
        }
        return loadAlertsPreferences(saved);
    } else if (action === "add") {
        alertsUi.draft = blankAlertDraft();
        alertsUi.editingId = "";
        alertsUi.view = "edit";
        alertsUi.error = "";
        paintAlerts("alertsBrand");
    } else if (action === "edit") {
        const rule = ((alertsUi.prefs && alertsUi.prefs.rules) || []).find(item => item.id === id);
        if (!rule) return;
        alertsUi.draft = draftFromRule(rule);
        alertsUi.editingId = id;
        alertsUi.view = "edit";
        alertsUi.error = "";
        paintAlerts("alertsBrand");
    } else if (action === "remove") {
        return removeAlert(id);
    } else if (action === "cancel-edit") {
        alertsUi.view = "manage";
        alertsUi.error = "";
        alertsUi.editingId = "";
        paintAlerts();
    } else if (action === "unsubscribe" || action === "delete") {
        alertsUi.confirm = action;
        alertsUi.view = "manage";
        paintAlerts();
    } else if (action === "cancel-confirm") {
        alertsUi.confirm = "";
        paintAlerts();
    } else if (action === "confirm-unsubscribe") {
        return finishSubscription("unsubscribe");
    } else if (action === "confirm-delete") {
        return finishSubscription("delete");
    }
}

function ensureAlertsShell() {
    if (document.getElementById("alertsRoot")) return;
    const root = alertsEl("div", "");
    root.id = "alertsRoot";
    setHidden(root, true);
    const panel = alertsEl("div", "alerts-panel");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-labelledby", "alertsTitle");
    const head = alertsEl("div", "alerts-head");
    const title = alertsEl("h2", "alerts-title", "Alerts");
    title.id = "alertsTitle";
    const close = alertsEl("button", "alerts-close", "Close");
    close.type = "button";
    close.setAttribute("aria-label", "Close alerts");
    close.addEventListener("click", closeAlerts);
    head.append(title, close);
    const live = alertsEl("p", "alerts-live", "");
    live.id = "alertsLive";
    live.setAttribute("role", "status");
    const error = alertsEl("p", "alerts-error", "");
    error.id = "alertsError";
    error.setAttribute("role", "alert");
    const body = alertsEl("div", "alerts-body");
    body.id = "alertsBody";
    panel.append(head, live, error, body);
    root.appendChild(panel);
    root.addEventListener("click", event => {
        if (event.target === root) closeAlerts();
    });
    body.addEventListener("click", onAlertsClick);
    if (document.body) document.body.appendChild(root);
}

function mountAlertsNav() {
    if (document.getElementById("navAlerts")) return;
    const nav = document.querySelector ? document.querySelector(".topnav-links") : null;
    if (!nav) return;
    const button = alertsEl("button", "nav-link nav-alerts", "Subscribe");
    button.id = "navAlerts";
    button.type = "button";
    button.setAttribute("aria-label", "Subscribe to SkateDeals deal emails");
    button.addEventListener("click", () => openAlerts());
    nav.appendChild(button);
}

function isAlertsOpen() {
    const root = document.getElementById("alertsRoot");
    return !!(alertsUi.open && root && !root.hidden);
}

function closeAlerts() {
    alertsUi.open = false;
    setHidden(document.getElementById("alertsRoot"), true);
    if (document.body && document.body.classList) document.body.classList.remove("alerts-open");
    if (alertsUi.returnFocus && alertsUi.returnFocus.focus) alertsUi.returnFocus.focus();
}

function alertsPanel() {
    const root = document.getElementById("alertsRoot");
    if (!root || !root.querySelector) return null;
    return root.querySelector(".alerts-panel");
}

function alertsHiddenByClosedDetails(node) {
    let parent = node.parentElement || node.parent || null;
    while (parent) {
        const tag = String(parent.tagName || parent.tag || "").toLowerCase();
        if (tag === "details" && !parent.open) {
            const nodeTag = String(node.tagName || node.tag || "").toLowerCase();
            const nodeParent = node.parentElement || node.parent || null;
            if (nodeTag === "summary" && nodeParent === parent) return false;
            return true;
        }
        parent = parent.parentElement || parent.parent || null;
    }
    return false;
}

function alertsIsTabStop(node) {
    const tag = String(node.tagName || node.tag || "").toLowerCase();
    if (["a", "button", "input", "select", "textarea", "summary"].indexOf(tag) < 0) return false;
    if (node.disabled) return false;
    if (node.hidden) return false;
    if (node.tabIndex < 0) return false;
    if (alertsHiddenByClosedDetails(node)) return false;
    return true;
}

function alertsTabStops(panel) {
    const stops = [];
    const visit = node => {
        const kids = (node && node.children) || [];
        for (let i = 0; i < kids.length; i++) {
            const child = kids[i];
            if (!child) continue;
            if (alertsIsTabStop(child)) stops.push(child);
            visit(child);
        }
    };
    visit(panel);
    return stops;
}

function onAlertsKeydown(event) {
    if (!isAlertsOpen() || !event) return;
    if (event.key === "Escape") {
        if (event.preventDefault) event.preventDefault();
        closeAlerts();
        return;
    }
    if (event.key !== "Tab") return;
    const panel = alertsPanel();
    if (!panel) return;
    const stops = alertsTabStops(panel);
    if (!stops.length) return;
    const active = document.activeElement;
    const first = stops[0];
    const last = stops[stops.length - 1];
    const inside = panel.contains ? panel.contains(active) : false;
    if (event.shiftKey) {
        if (!inside || active === first) {
            if (event.preventDefault) event.preventDefault();
            if (last.focus) last.focus();
        }
        return;
    }
    if (!inside || active === last) {
        if (event.preventDefault) event.preventDefault();
        if (first.focus) first.focus();
    }
}

async function openAlerts(options) {
    options = options || {};
    ensureAlertsShell();
    alertsUi.returnFocus = options.returnFocus || (typeof document !== "undefined" && document.activeElement) || null;
    alertsUi.config = alertsPageConfig();
    alertsUi.client = createAlertsClient(alertsUi.config);
    alertsUi.open = true;
    alertsUi.error = "";
    alertsUi.message = "";
    alertsUi.confirm = "";
    alertsUi.active = false;
    alertsUi.health = null;
    alertsUi.healthUnread = false;
    alertsUi.consent = false;
    alertsUi.broad = false;
    alertsUi.trigger = "below";
    if (document.body && document.body.classList) document.body.classList.add("alerts-open");
    setHidden(document.getElementById("alertsRoot"), false);
    if (options.draft) alertsUi.draft = options.draft;
    if (!alertsUi.draft) alertsUi.draft = blankAlertDraft();
    alertsUi.entry = alertsEntryFromDraft(alertsUi.draft);
    if (alertsUi.config.mode !== "live") {
        alertsUi.view = "soon";
        alertsUi.prefs = null;
        paintAlerts();
        return;
    }
    if (options.fragment && options.fragment.purpose === "verify") {
        await verifyAlertsToken(options.fragment.token);
        return;
    }
    if (options.fragment && options.fragment.purpose === "manage") {
        await loadAlertsPreferences(options.fragment.token);
        return;
    }
    if (options.manage) {
        const saved = readManageToken();
        if (saved) {
            await loadAlertsPreferences(saved);
            return;
        }
    }
    alertsUi.view = "signup";
    alertsUi.prefs = null;
    await refreshHealth();
    paintAlerts(alertsUi.view === "down" ? "" : "alertsEmail");
}

function appendQuickAlert(parent, card) {
    const button = alertsEl("button", "quick-alert", "Alert me");
    button.type = "button";
    button.setAttribute("aria-label", "Alert me about this deal");
    button.addEventListener("click", event => {
        if (event.stopPropagation) event.stopPropagation();
        if (event.preventDefault) event.preventDefault();
        const dataset = (card && card.dataset) || {};
        const draft = alertDraftFromDataset(dataset);
        draft.image = alertsProductImage(card);
        const returnFocus = card && typeof card.querySelector === "function" ? card.querySelector(".card-more") : button;
        if (typeof closeQuickView === "function") closeQuickView();
        openAlerts({ draft: draft, returnFocus: returnFocus });
    });
    parent.appendChild(button);
}

function wireAlerts() {
    if (alertsUi.wired) return;
    alertsUi.wired = true;
    mountAlertsNav();
    ensureAlertsShell();
    if (typeof document !== "undefined" && document.addEventListener) {
        document.addEventListener("keydown", onAlertsKeydown);
    }
    if (typeof window !== "undefined" && window.addEventListener) {
        window.addEventListener("hashchange", () => {
            const parsed = consumeAlertsFragment();
            if (parsed) openAlerts({ fragment: parsed });
        });
    }
    const parsed = consumeAlertsFragment();
    if (parsed) openAlerts({ fragment: parsed });
}

if (typeof document !== "undefined") document.addEventListener("DOMContentLoaded", wireAlerts);

/* ALERTS_UI_END */




