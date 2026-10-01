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
    sortDir: "asc"
};

const STAR_KEY = "salesscraper2.stars";
const SNAP_KEY = "salesscraper2.snapshot";
let visitGone = [];

function catalog() {
    const node = document.getElementById("catalogJson");
    if (!node) return { items: {} };
    try {
        return JSON.parse(node.textContent);
    } catch (err) {
        return { items: {} };
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

function readControls() {
    const search = document.getElementById("searchInput");
    state.search = search ? search.value.toLowerCase().trim() : "";
    state.priceMin = numOrNull("priceMin");
    state.priceMax = numOrNull("priceMax");
    state.discountMin = numOrNull("discountMin");
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

function applyFilters() {
    readControls();
    dealRows().forEach(row => {
        row.classList.toggle("filtered-out", !rowMatches(row));
    });
    const removedOn = state.change === "removed";
    const deals = document.getElementById("dealsSection");
    const removed = document.getElementById("removedSection");
    if (deals) deals.hidden = removedOn;
    if (removed && removedOn) {
        removed.hidden = false;
        const content = removed.querySelector(".section-content");
        if (content) content.classList.remove("collapsed");
        const header = removed.querySelector(".section-header");
        if (header) header.classList.remove("collapsed");
    }
    applyGroupVisibility();
    syncDetails();
    paintCards();
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
        const removed = document.getElementById("removedSection");
        if (removed) removed.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

function sortBy(key, direction) {
    const tbody = document.querySelector("#mainTable tbody");
    if (!tbody) return;
    const numeric = { price: 1, original: 1, discount: 1, size: 1, days: 1, score: 1, rank: 1 };
    if (!direction) {
        if (state.sortKey === key) direction = state.sortDir === "asc" ? "desc" : "asc";
        else direction = key === "price" || key === "rank" || key === "store" || key === "brand" || key === "size" ? "asc" : "desc";
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
    document.querySelectorAll("#mainTable th").forEach(th => th.classList.remove("sorted"));
    const header = document.querySelector('#mainTable th[data-sort="' + key + '"]');
    if (header) header.classList.add("sorted");
}

function sortTable() {
    sortBy("price");
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
        search: ""
    };
    const search = document.getElementById("searchInput");
    if (search) search.value = "";
    ["priceMin", "priceMax", "discountMin"].forEach(id => {
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
    const bar = document.querySelector(".sticky-bar");
    if (!bar) return;
    document.documentElement.style.setProperty("--stick-top", bar.offsetHeight + "px");
}

function updateAgo() {
    const node = document.getElementById("lastScan");
    if (!node) return;
    const raw = node.getAttribute("datetime") || "";
    const parsed = Date.parse(raw.replace(" ", "T") + "Z");
    if (!Number.isFinite(parsed)) return;
    const seconds = Math.max(0, (Date.now() - parsed) / 1000);
    let label = raw;
    if (seconds < 90) label = "just now";
    else if (seconds < 5400) label = Math.round(seconds / 60) + " minutes ago";
    else if (seconds < 129600) label = Math.round(seconds / 3600) + " hours ago";
    else label = Math.round(seconds / 86400) + " days ago";
    node.textContent = label;
}

function init() {
    prepareVisit();
    applyStars();
    updateAgo();
    measureBar();
    window.addEventListener("resize", measureBar);
    const search = document.getElementById("searchInput");
    if (search) search.addEventListener("input", applyFilters);
    ["priceMin", "priceMax", "discountMin"].forEach(id => {
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
    const close = document.getElementById("drawerClose");
    if (close) close.addEventListener("click", closeDrawer);
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") closeDrawer();
    });
    updateChangeLine();
    applyFilters();
}

document.addEventListener("DOMContentLoaded", init);
