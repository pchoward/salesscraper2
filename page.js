let state = {
    store: "all",
    part: "all",
    size: "all",
    brand: "all",
    length: "all",
    wheelbase: "all",
    watching: false,
    cardNew: false,
    cardDrop: false,
    cardLow: false,
    change: "all",
    grouped: false,
    visitMode: "yesterday",
    sortKey: "rank",
    sortDir: "asc",
    search: "",
    wmin: null,
    wmax: null
};

const STAR_KEY = "salesscraper2.stars";
const SNAP_KEY = "salesscraper2.snapshot";
const VIEWS_KEY = "salesscraper2.views";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
let visitGone = [];
let sparkTip = null;
let renamingId = "";

function catalog() {
    const node = document.getElementById("catalogJson");
    if (!node) return { items: {}, views: [] };
    try {
        return JSON.parse(node.textContent);
    } catch (err) {
        return { items: {}, views: [] };
    }
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

function dealRows() {
    return Array.from(document.querySelectorAll("#mainTable .deal-row"));
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

function readControls() {
    const search = document.getElementById("searchInput");
    state.search = search ? search.value.toLowerCase().trim() : "";
    state.priceMin = numOrNull("priceMin");
    state.priceMax = numOrNull("priceMax");
    state.discountMin = numOrNull("discountMin");
    state.wmin = numOrNull("widthMin");
    state.wmax = numOrNull("widthMax");
    const brand = document.getElementById("brandSelect");
    const width = document.getElementById("widthSelect");
    const length = document.getElementById("lengthSelect");
    const wheelbase = document.getElementById("wheelbaseSelect");
    if (width) state.size = width.value || "all";
    if (brand) state.brand = brand.value || "all";
    if (length) state.length = length.value || "all";
    if (wheelbase) state.wheelbase = wheelbase.value || "all";
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
        button.setAttribute("aria-pressed", button.getAttribute("data-change") === state.change ? "true" : "false");
    });
}

function rowMatches(row) {
    const hay = (row.dataset.search || "").toLowerCase();
    if (state.search && !hay.includes(state.search)) return false;
    if (state.store !== "all" && (row.dataset.store || "") !== state.store) return false;
    if (state.part !== "all" && (row.dataset.part || "") !== state.part) return false;
    if (state.size !== "all" && (row.dataset.size || "") !== state.size) return false;
    if (state.size === "all" && (state.wmin != null || state.wmax != null)) {
        const size = parseFloat(row.dataset.size);
        if (!Number.isFinite(size)) return false;
        if (state.wmin != null && size < state.wmin - 1e-6) return false;
        if (state.wmax != null && size > state.wmax + 1e-6) return false;
    }
    if (state.brand !== "all" && (row.dataset.brand || "") !== state.brand) return false;
    if (state.length !== "all" && (row.dataset.length || "") !== state.length) return false;
    if (state.wheelbase !== "all" && (row.dataset.wheelbase || "") !== state.wheelbase) return false;
    const price = parseFloat(row.dataset.price);
    if (state.priceMin != null && !(price >= state.priceMin)) return false;
    if (state.priceMax != null && !(price <= state.priceMax)) return false;
    if (state.discountMin != null) {
        if (row.dataset.discount === "") return false;
        if (parseFloat(row.dataset.discount) < state.discountMin) return false;
    }
    if (state.watching && row.dataset.starred !== "1") return false;
    if (state.cardNew && row.dataset.added !== "1") return false;
    if (state.cardDrop && row.dataset.drop !== "1") return false;
    if (state.cardLow && row.dataset.lowest !== "1") return false;
    const added = state.visitMode === "visit" ? row.dataset.visitNew : row.dataset.added;
    const drop = state.visitMode === "visit" ? row.dataset.visitDrop : row.dataset.drop;
    const low = state.visitMode === "visit" ? row.dataset.visitLow : row.dataset.hitlow;
    if (state.change === "new" && added !== "1") return false;
    if (state.change === "drop" && drop !== "1") return false;
    if (state.change === "lowest" && low !== "1") return false;
    if (state.change === "removed") return false;
    return true;
}

function syncDetails() {
    document.querySelectorAll(".detail-row").forEach(detail => {
        const row = document.querySelector('.deal-row[data-id="' + detail.dataset.for + '"]');
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

function applyFilters() {
    readControls();
    dealRows().forEach(row => {
        row.classList.toggle("filtered-out", !rowMatches(row));
    });
    const removedOn = state.change === "removed";
    const deals = document.getElementById("dealsSection");
    if (deals) deals.hidden = removedOn;
    showGone(removedOn);
    applyGroupVisibility();
    syncDetails();
    paintCards();
    updateMoreCount();
    syncUrl();
    paintViews();
}

function filterProducts() {
    applyFilters();
}

function filterByStore(store) {
    state.store = store || "all";
    const select = document.getElementById("storeSelect");
    if (select) select.value = state.store;
    setPressed("#storeFilters .filter-btn", "data-store", state.store);
    applyFilters();
}

function filterByPart(part) {
    state.part = part || "all";
    const select = document.getElementById("partSelect");
    if (select) select.value = state.part;
    setPressed("#partFilters .filter-btn", "data-part", state.part);
    applyFilters();
}

function filterBySize(size) {
    state.size = size || "all";
    const select = document.getElementById("widthSelect");
    if (select) select.value = state.size;
    if (state.size !== "all") {
        const wmin = document.getElementById("widthMin");
        const wmax = document.getElementById("widthMax");
        if (wmin) wmin.value = "";
        if (wmax) wmax.value = "";
        state.wmin = null;
        state.wmax = null;
    }
    setPressed("#sizeFilters .chip", "data-size", state.size);
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
        setPressed("#storeFilters .filter-btn", "data-store", state.store);
    } else if (kind === "clear") {
        state.cardNew = false;
        state.cardDrop = false;
        state.cardLow = false;
        state.store = "all";
        state.change = "all";
        const select = document.getElementById("storeSelect");
        if (select) select.value = "all";
        setPressed("#storeFilters .filter-btn", "data-store", "all");
    }
    applyFilters();
}

function setChange(kind) {
    state.change = state.change === kind ? "all" : kind;
    if (kind === "new") state.cardNew = state.change === "new";
    if (kind === "drop") state.cardDrop = state.change === "drop";
    if (kind === "lowest") state.cardLow = state.change === "lowest";
    applyFilters();
    if (state.change === "removed") {
        const gone = document.getElementById("goneSection");
        if (gone) gone.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

function sortBy(key, direction) {
    const tbody = document.querySelector("#mainTable tbody");
    if (!tbody) return;
    const numeric = { price: 1, original: 1, discount: 1, size: 1, days: 1, daysat: 1, score: 1, rank: 1 };
    if (!direction) {
        if (state.sortKey === key) direction = state.sortDir === "asc" ? "desc" : "asc";
        else direction = key === "price" || key === "rank" || key === "store" || key === "brand" || key === "size" || key === "daysat" ? "asc" : "desc";
    }
    state.sortKey = key;
    state.sortDir = direction;
    const rows = Array.from(tbody.querySelectorAll(".deal-row"));
    rows.sort((a, b) => {
        if (key === "rank") return (parseFloat(a.dataset.rank) || 0) - (parseFloat(b.dataset.rank) || 0);
        const av = a.dataset[key];
        const bv = b.dataset[key];
        const aMissing = av === undefined || av === "";
        const bMissing = bv === undefined || bv === "";
        if (aMissing && bMissing) return 0;
        if (aMissing) return 1;
        if (bMissing) return -1;
        if (numeric[key]) {
            const diff = parseFloat(av) - parseFloat(bv);
            return direction === "asc" ? diff : -diff;
        }
        const diff = String(av).localeCompare(String(bv));
        return direction === "asc" ? diff : -diff;
    });
    rows.forEach(row => {
        const detail = document.querySelector('.detail-row[data-for="' + row.dataset.id + '"]');
        tbody.appendChild(row);
        if (detail) tbody.appendChild(detail);
    });
    document.querySelectorAll("#mainTable [data-sort]").forEach(node => node.classList.remove("sorted"));
    const header = document.querySelector('#mainTable [data-sort="' + key + '"]');
    if (header) header.classList.add("sorted");
    mirrorSort(key, direction);
    syncUrl();
}

function sortTable() {
    sortBy("price");
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
    dealRows().forEach(row => {
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
    const row = button.closest(".deal-row");
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
        btnNew: plural(added, "new deal", "new deals"),
        btnDrop: plural(drop, "price drop", "price drops"),
        btnLow: low + " hit lowest tracked price",
        btnGone: plural(gone, "deal disappeared", "deals disappeared")
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
    updateChangeLine();
    applyFilters();
}

function prepareVisit() {
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
        Object.keys(previous.items).forEach(url => {
            if (!current[url]) gone.push(previous.items[url]);
        });
        visitGone = gone;
        if (note) {
            note.dataset.message = "1";
            const when = previous.at ? " Last visit " + previous.at + "." : "";
            note.textContent = gone.length
                ? "Left since that visit: " + gone.map(item => item.name).slice(0, 8).join(", ") + when
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
        part: "all",
        size: "all",
        brand: "all",
        length: "all",
        wheelbase: "all",
        watching: false,
        cardNew: false,
        cardDrop: false,
        cardLow: false,
        change: "all",
        grouped: state.grouped,
        visitMode: state.visitMode,
        sortKey: "rank",
        sortDir: "asc",
        search: "",
        wmin: null,
        wmax: null
    };
    const search = document.getElementById("searchInput");
    if (search) search.value = "";
    ["priceMin", "priceMax", "discountMin", "widthMin", "widthMax"].forEach(id => {
        const node = document.getElementById(id);
        if (node) node.value = "";
    });
    ["storeSelect", "partSelect", "widthSelect", "brandSelect", "lengthSelect", "wheelbaseSelect"].forEach(id => {
        const node = document.getElementById(id);
        if (node) node.value = "all";
    });
    const sort = document.getElementById("sortSelect");
    if (sort) sort.value = "rank";
    const watching = document.getElementById("watchingToggle");
    if (watching) watching.setAttribute("aria-pressed", "false");
    setPressed("#storeFilters .filter-btn", "data-store", "all");
    setPressed("#partFilters .filter-btn", "data-part", "all");
    setPressed("#sizeFilters .chip", "data-size", "all");
    sortBy("rank", "asc");
    applyFilters();
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
    return { zumiez: "Zumiez", skatewarehouse: "SkateWarehouse", ccs: "CCS", tactics: "Tactics" }[key] || "";
}

function slugType(value) {
    const key = String(value || "").trim().toLowerCase();
    return {
        deck: "Decks",
        decks: "Decks",
        wheel: "Wheels",
        wheels: "Wheels",
        truck: "Trucks",
        trucks: "Trucks",
        bearing: "Bearings",
        bearings: "Bearings"
    }[key] || "";
}

function storeSlug(name) {
    return { Zumiez: "zumiez", SkateWarehouse: "skatewarehouse", CCS: "ccs", Tactics: "tactics" }[name] || "";
}

function typeSlug(name) {
    return { Decks: "deck", Wheels: "wheel", Trucks: "truck", Bearings: "bearing" }[name] || "";
}

function flagOn(value) {
    return ["1", "true", "yes", "on"].indexOf(String(value || "").toLowerCase()) >= 0;
}

function decodeQuery(query) {
    const stateOut = {
        q: "",
        store: "all",
        part: "all",
        width: "all",
        wmin: null,
        wmax: null,
        brand: "all",
        min: null,
        max: null,
        discount: null,
        length: "all",
        wheelbase: "all",
        sort: "rank",
        change: "all",
        watching: false,
        low: false,
        added: false,
        dropped: false,
        grouped: false
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
            if (value.indexOf("-") >= 0) {
                const bits = value.split("-");
                stateOut.width = "all";
                stateOut.wmin = bits[0] === "" ? null : Number(bits[0]);
                stateOut.wmax = bits[1] === "" ? null : Number(bits[1]);
                if (stateOut.wmin != null && !Number.isFinite(stateOut.wmin)) stateOut.wmin = null;
                if (stateOut.wmax != null && !Number.isFinite(stateOut.wmax)) stateOut.wmax = null;
            } else if (value && value !== "all") {
                const number = Number(value);
                stateOut.width = Number.isFinite(number) ? numText(number) : "all";
            }
        } else if (key === "brand" && value.trim()) stateOut.brand = value.trim();
        else if (key === "min") stateOut.min = Number(value);
        else if (key === "max") stateOut.max = Number(value);
        else if (key === "discount") stateOut.discount = Number(value);
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
    });
    ["min", "max", "discount"].forEach(key => {
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
    if (snapshot.part && snapshot.part !== "all") add("type", typeSlug(snapshot.part));
    if (snapshot.width && snapshot.width !== "all") add("width", snapshot.width);
    else if (snapshot.wmin != null || snapshot.wmax != null) {
        const left = snapshot.wmin != null ? numText(snapshot.wmin) : "";
        const right = snapshot.wmax != null ? numText(snapshot.wmax) : "";
        add("width", left + "-" + right);
    }
    add("brand", snapshot.brand || "");
    if (snapshot.min != null) add("min", numText(snapshot.min));
    if (snapshot.max != null) add("max", numText(snapshot.max));
    if (snapshot.discount != null) add("discount", numText(snapshot.discount));
    add("length", snapshot.length || "");
    add("wheelbase", snapshot.wheelbase || "");
    if (snapshot.sort && snapshot.sort !== "rank") add("sort", snapshot.sort);
    if (["new", "drop", "lowest", "removed"].indexOf(snapshot.change) >= 0) add("change", snapshot.change);
    if (snapshot.watching) add("watching", "1");
    if (snapshot.low && snapshot.change !== "lowest") add("low", "1");
    if (snapshot.added && snapshot.change !== "new") add("added", "1");
    if (snapshot.dropped && snapshot.change !== "drop") add("dropped", "1");
    if (snapshot.grouped) add("group", "1");
    return params.toString();
}

function captureState() {
    readControls();
    const sort = document.getElementById("sortSelect");
    return {
        q: (document.getElementById("searchInput") || {}).value || "",
        store: state.store,
        part: state.part,
        width: state.size,
        wmin: state.wmin,
        wmax: state.wmax,
        brand: state.brand,
        min: state.priceMin,
        max: state.priceMax,
        discount: state.discountMin,
        length: state.length,
        wheelbase: state.wheelbase,
        sort: sort ? sort.value : "rank",
        change: state.change,
        watching: state.watching,
        low: state.cardLow,
        added: state.cardNew,
        dropped: state.cardDrop,
        grouped: state.grouped
    };
}

function setSelect(id, value) {
    const node = document.getElementById(id);
    if (!node) return;
    const has = Array.from(node.options || []).some(option => option.value === value);
    node.value = has ? value : (value === "all" || !value ? "all" : node.value);
    if (!has && value && value !== "all") node.value = "all";
}

function writeControls(snapshot) {
    const search = document.getElementById("searchInput");
    if (search) search.value = snapshot.q || "";
    setSelect("storeSelect", snapshot.store || "all");
    setSelect("partSelect", snapshot.part || "all");
    setSelect("widthSelect", snapshot.width || "all");
    setSelect("brandSelect", snapshot.brand || "all");
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
    fill("widthMin", snapshot.width !== "all" ? null : snapshot.wmin);
    fill("widthMax", snapshot.width !== "all" ? null : snapshot.wmax);
    state.store = snapshot.store || "all";
    state.part = snapshot.part || "all";
    state.size = snapshot.width || "all";
    state.brand = snapshot.brand || "all";
    state.length = snapshot.length || "all";
    state.wheelbase = snapshot.wheelbase || "all";
    state.change = snapshot.change || "all";
    state.watching = !!snapshot.watching;
    state.grouped = !!snapshot.grouped;
    state.cardLow = !!snapshot.low || snapshot.change === "lowest";
    state.cardNew = !!snapshot.added || snapshot.change === "new";
    state.cardDrop = !!snapshot.dropped || snapshot.change === "drop";
    const watching = document.getElementById("watchingToggle");
    if (watching) watching.setAttribute("aria-pressed", state.watching ? "true" : "false");
    const grouped = document.getElementById("groupToggle");
    if (grouped) grouped.setAttribute("aria-pressed", state.grouped ? "true" : "false");
    setPressed("#storeFilters .filter-btn", "data-store", state.store);
    setPressed("#partFilters .filter-btn", "data-part", state.part);
    setPressed("#sizeFilters .chip", "data-size", state.size);
}

function syncUrl() {
    try {
        const query = encodeState(captureState());
        const next = query ? "?" + query : location.pathname;
        const current = location.pathname + location.search;
        const target = query ? location.pathname + "?" + query : location.pathname;
        if (current !== target) history.replaceState(null, "", next);
    } catch (err) {
        /* a bad URL must not break filtering */
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
        tab.className = "view-tab" + (view.query === current ? " on" : "");
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
    ["priceMin", "priceMax", "discountMin", "widthMin", "widthMax"].forEach(id => {
        if (numOrNull(id) != null) count += 1;
    });
    const length = document.getElementById("lengthSelect");
    const wheel = document.getElementById("wheelbaseSelect");
    if (length && length.value && length.value !== "all") count += 1;
    if (wheel && wheel.value && wheel.value !== "all") count += 1;
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

function showSparkTip(event, point) {
    const tip = ensureSparkTip();
    if (!tip || !point) return;
    tip.hidden = false;
    tip.textContent = shortDate(point[0]) + " · $" + Number(point[1]).toFixed(2);
    tip.style.left = Math.min(window.innerWidth - 140, event.clientX + 12) + "px";
    tip.style.top = (event.clientY + 14) + "px";
}

function hideSparkTip() {
    const tip = ensureSparkTip();
    if (tip) tip.hidden = true;
}

function nearestPoint(id, event, svg) {
    const item = (catalog().items || {})[id];
    const points = item && Array.isArray(item.daily) && item.daily.length ? item.daily : (item && item.series) || [];
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

function init() {
    prepareVisit();
    applyStars();
    updateAgo();
    updateBanners();
    measureBar();
    window.addEventListener("resize", measureBar);
    const bar = document.getElementById("stickyBar");
    if (bar && window.ResizeObserver) new ResizeObserver(measureBar).observe(bar);
    const search = document.getElementById("searchInput");
    if (search) search.addEventListener("input", applyFilters);
    ["priceMin", "priceMax", "discountMin", "widthMin", "widthMax"].forEach(id => {
        const node = document.getElementById(id);
        if (node) node.addEventListener("input", applyFilters);
    });
    const storeSelect = document.getElementById("storeSelect");
    if (storeSelect) storeSelect.addEventListener("change", () => filterByStore(storeSelect.value));
    const partSelect = document.getElementById("partSelect");
    if (partSelect) partSelect.addEventListener("change", () => filterByPart(partSelect.value));
    const widthSelect = document.getElementById("widthSelect");
    if (widthSelect) widthSelect.addEventListener("change", () => filterBySize(widthSelect.value));
    const brand = document.getElementById("brandSelect");
    if (brand) brand.addEventListener("change", applyFilters);
    const length = document.getElementById("lengthSelect");
    if (length) length.addEventListener("change", applyFilters);
    const wheelbase = document.getElementById("wheelbaseSelect");
    if (wheelbase) wheelbase.addEventListener("change", applyFilters);
    const sort = document.getElementById("sortSelect");
    if (sort) sort.addEventListener("change", applySortChoice);
    const more = document.getElementById("moreFilters");
    if (more) more.addEventListener("click", toggleMore);
    const save = document.getElementById("saveView");
    const form = document.getElementById("saveViewForm");
    if (save && form) {
        save.addEventListener("click", () => {
            form.hidden = false;
            const input = document.getElementById("viewNameInput");
            if (input) input.focus();
        });
    }
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
    dealRows().forEach(row => {
        row.addEventListener("click", event => {
            if (event.target.closest("a, button, input, select, label")) return;
            toggleDetail(row);
        });
        row.addEventListener("keydown", event => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                toggleDetail(row);
            }
        });
    });
    document.querySelectorAll(".star").forEach(button => {
        button.addEventListener("click", () => toggleStar(button));
    });
    document.querySelectorAll(".price-btn").forEach(button => {
        button.addEventListener("click", () => openDrawer(button.dataset.id));
    });
    document.querySelectorAll(".score-btn").forEach(button => {
        button.addEventListener("click", () => {
            const cell = button.closest(".score-cell");
            if (!cell) return;
            const pinned = cell.classList.toggle("pinned");
            button.setAttribute("aria-expanded", pinned ? "true" : "false");
        });
    });
    document.querySelectorAll(".spark-hit").forEach(button => {
        const svg = button.querySelector("svg");
        button.addEventListener("mousemove", event => {
            if (!svg) return;
            showSparkTip(event, nearestPoint(button.dataset.id, event, svg));
        });
        button.addEventListener("mouseleave", hideSparkTip);
        button.addEventListener("click", event => {
            event.stopPropagation();
            openSparkPanel(button.dataset.id, button);
        });
    });
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
            closeDrawer();
            closeSparkPanel();
        }
    });
    document.addEventListener("click", event => {
        const panel = document.getElementById("sparkPanel");
        if (!panel || panel.hidden) return;
        if (event.target.closest("#sparkPanel, .spark-hit")) return;
        closeSparkPanel();
    });
    updateChangeLine();
    paintViews();
    if (location.search && location.search.length > 1) loadFromUrl();
    else applyFilters();
}

document.addEventListener("DOMContentLoaded", init);
