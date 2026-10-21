"""Sidebar facets hide zero counts and keep counts clear of the scrollbar."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from report import build_report_html


ROOT = Path(__file__).resolve().parent


def _deck(price, url, store, name):
    return {
        "name": name,
        "url": url,
        "price_new": price,
        "price_old": "80.00",
        "part": "Decks",
        "store": store,
    }


class FacetVisibilityTests(unittest.TestCase):
    def test_scrollable_filter_lists_pad_for_the_scrollbar(self):
        page = (ROOT / "page.css").read_text(encoding="utf-8")
        mobile = (ROOT / "mobile.css").read_text(encoding="utf-8")
        html = build_report_html(
            {"Zumiez_Decks": [_deck("40.00", "https://example.com/d", "Zumiez", "Baker Team Deck 8.0")]},
            {},
            generated_at="2026-10-21T12:00:00+00:00",
        )
        for style in (page, mobile, html):
            self.assertIn("scrollbar-gutter: stable", style)
            self.assertIn("padding-inline-end: 12px", style)
        facet = page.split(".brand-facet .facet-list {", 1)[1].split("}", 1)[0]
        self.assertIn("overflow-y: auto", facet)
        self.assertIn("scrollbar-gutter: stable", facet)
        self.assertIn("padding-inline-end: 12px", facet)
        drawer = mobile.split(".rail .sidebar#filterDrawer {", 1)[-1]
        self.assertIn("scrollbar-gutter: stable", drawer)
        self.assertIn("padding-inline-end: 12px", drawer)
        hidden = page.split(".is-unavailable,", 1)[1].split("}", 1)[0]
        self.assertIn(".chip.is-zero:not([aria-pressed=\"true\"]):not(.is-partial)", hidden)
        self.assertIn("display: none !important;", hidden)
        zero = html.split('data-buckets="10up"', 1)[0][-80:]
        self.assertIn('class="chip width-chip is-zero"', zero)

    def test_zero_counts_hide_and_same_group_options_stay(self):
        source = (ROOT / "page.js").read_text(encoding="utf-8")
        self.assertIn("function markFacetOption(", source)
        self.assertIn('rowMatches(row, { brand: "all" })', source)
        self.assertIn('rowMatches(row, { store: "all" })', source)
        self.assertIn('rowMatches(row, { widths: [] })', source)
        self.assertIn("override[facet.stateKey] = []", source)
        script = r"""
const assert = require("node:assert/strict");
class El {
    constructor(tag) {
        this.tag = tag || "div";
        this.children = [];
        this.attrs = {};
        this.className = "";
        this._text = "";
        this._value = "";
        this._hidden = false;
        this.disabled = false;
        this.parent = null;
        this.id = "";
        this.dataset = {};
    }
    append(...nodes) {
        nodes.forEach(node => this.appendChild(node));
    }
    appendChild(node) {
        if (!node) return node;
        if (node.parent && node.parent.removeChild) node.parent.removeChild(node);
        node.parent = this;
        this.children.push(node);
        return node;
    }
    removeChild(node) {
        this.children = this.children.filter(child => child !== node);
        if (node && node.parent === this) node.parent = null;
        return node;
    }
    setAttribute(name, value) {
        this.attrs[name] = String(value);
        if (name === "id") this.id = String(value);
        if (name === "class") this.className = String(value);
        if (name === "hidden") this._hidden = true;
    }
    getAttribute(name) {
        return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null;
    }
    removeAttribute(name) {
        delete this.attrs[name];
        if (name === "hidden") this._hidden = false;
    }
    hasAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attrs, name); }
    get hidden() { return !!this._hidden; }
    set hidden(value) {
        this._hidden = !!value;
        if (this._hidden) this.attrs.hidden = "";
        else delete this.attrs.hidden;
    }
    get value() {
        if (this.tag === "option") return this.getAttribute("value") || "";
        return this._value == null ? "" : String(this._value);
    }
    set value(value) { this._value = value == null ? "" : String(value); }
    get parentNode() { return this.parent; }
    get options() {
        if (this.tag !== "select") return undefined;
        return this.children.filter(child => child.tag === "option");
    }
    get textContent() {
        if (this.children.length) return this.children.map(child => child.textContent || "").join("");
        return this._text;
    }
    set textContent(value) {
        this._text = String(value);
        this.children = [];
    }
    get classList() {
        const el = this;
        return {
            contains(name) { return el.className.split(/\s+/).filter(Boolean).includes(name); },
            add(...names) {
                names.forEach(name => {
                    if (!el.classList.contains(name)) el.className = (el.className + " " + name).trim();
                });
            },
            remove(...names) {
                el.className = el.className.split(/\s+/).filter(part => part && !names.includes(part)).join(" ");
            },
            toggle(name, force) {
                const has = el.classList.contains(name);
                const next = force === undefined ? !has : !!force;
                if (next) el.classList.add(name);
                else el.classList.remove(name);
                return next;
            }
        };
    }
    matches(sel) {
        if (!sel || sel === "*") return true;
        let rest = sel;
        while (rest) {
            if (rest[0] === ".") {
                const match = /^[\w-]+/.exec(rest.slice(1));
                if (!match || !this.classList.contains(match[0])) return false;
                rest = rest.slice(1 + match[0].length);
            } else if (rest[0] === "#") {
                const match = /^[\w-]+/.exec(rest.slice(1));
                if (!match || this.id !== match[0]) return false;
                rest = rest.slice(1 + match[0].length);
            } else if (rest[0] === "[") {
                const end = rest.indexOf("]");
                const body = rest.slice(1, end);
                const eq = /^([\w-]+)="([^"]*)"$/.exec(body);
                if (eq) {
                    if ((this.getAttribute(eq[1]) || "") !== eq[2]) return false;
                } else if (!this.hasAttribute(body)) return false;
                rest = rest.slice(end + 1);
            } else {
                const match = /^[\w-]+/.exec(rest);
                if (!match || this.tag !== match[0]) return false;
                rest = rest.slice(match[0].length);
            }
        }
        return true;
    }
    querySelectorAll(sel) { return queryAll(this, sel); }
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}
function descendants(node) {
    const found = [];
    (node.children || []).forEach(child => {
        found.push(child);
        descendants(child).forEach(item => found.push(item));
    });
    return found;
}
function queryAll(root, selector) {
    const tokens = selector.trim().split(/\s+/);
    let nodes = [root];
    let direct = false;
    tokens.forEach(token => {
        if (token === ">") { direct = true; return; }
        if (token === ":scope") return;
        const next = [];
        nodes.forEach(start => {
            const pool = direct ? (start.children || []) : descendants(start);
            pool.forEach(node => { if (node.matches(token)) next.push(node); });
        });
        nodes = next;
        direct = false;
    });
    return nodes;
}
function walk(node, visit) {
    if (!node) return;
    visit(node);
    (node.children || []).forEach(child => walk(child, visit));
}
const body = new El("body");
const document = {
    body: body,
    events: {},
    createElement(tag) { return new El(tag); },
    addEventListener(name, fn) { (this.events[name] = this.events[name] || []).push(fn); },
    getElementById(id) {
        let found = null;
        walk(body, node => { if (!found && node.id === id) found = node; });
        return found;
    },
    querySelector(sel) { return queryAll(body, sel)[0] || null; },
    querySelectorAll(sel) { return queryAll(body, sel); }
};
global.document = document;
global.window = global;
global.requestAnimationFrame = function () {};
const WIDTH_RANGES = [
    { id: "8.0-8.125", label: "8.0 - 8.125", min: 8.0, max: 8.125 },
    { id: "8.125-8.25", label: "8.125 - 8.25", min: 8.125, max: 8.25 },
    { id: "8.5-8.75", label: "8.5 - 8.75", min: 8.5, max: 8.75 },
    { id: "10up", label: "10.0+", min: 10.0, max: null }
];
function h(tag, attrs, kids) {
    const node = new El(tag);
    Object.keys(attrs || {}).forEach(key => {
        if (key === "class") node.className = attrs[key];
        else if (key === "id") node.id = attrs[key];
        else if (key === "text") node._text = attrs[key];
        else if (key === "value") {
            node.setAttribute("value", attrs[key]);
            node._value = attrs[key];
        } else node.setAttribute(key, attrs[key]);
    });
    (kids || []).forEach(child => node.appendChild(child));
    return node;
}
function span(className, text) {
    return h("span", { class: className, text: text });
}
function button(className, attrs, kids) {
    return h("button", Object.assign({ class: className }, attrs), kids);
}
function option(value, label) {
    return h("option", { value: value, "data-label": label, text: label });
}
function select(id, values) {
    return h("select", { id: id }, values.map(value => option(value, value === "all" ? "All" : value)));
}
function chip(className, attr, value, countClass) {
    return button(className, { [attr]: value, "aria-pressed": "false" }, [
        span(countClass === "facet-count" ? "facet-name" : "label", value),
        span(countClass, "0")
    ]);
}
const table = h("table", { id: "mainTable" });
const tbody = h("tbody");
table.appendChild(tbody);
function row(data) {
    const node = h("tr", { class: "deal-row" });
    node.dataset = data;
    tbody.appendChild(node);
    return node;
}
row({ id: "b1", store: "Zumiez", part: "Decks", brand: "Baker", size: "8.0", length: "31", search: "baker deck", price: "40", discount: "", fresh: "1", drop: "0" });
row({ id: "g1", store: "CCS", part: "Decks", brand: "Girl", size: "8.5", length: "32", search: "girl deck", price: "45", discount: "", fresh: "0", drop: "1" });
row({ id: "s1", store: "CCS", part: "Sneakers", brand: "Vans", size: "", shoesize: "8", search: "vans shoe size 9.5", price: "50", discount: "" });
row({ id: "w1", store: "Zumiez", part: "Wheels", brand: "Spitfire", size: "", diameter: "52-53", search: "spitfire", price: "30", discount: "" });
row({ id: "w2", store: "Tactics", part: "Wheels", brand: "Bones", size: "", diameter: "54-55", search: "bones", price: "28", discount: "" });
const brandList = h("div", { id: "brandList", class: "facet-list" }, [
    button("facet-value", { "data-brand": "all", "aria-pressed": "true" }, [span("facet-name", "All brands")]),
    chip("facet-value", "data-brand", "Baker", "facet-count"),
    chip("facet-value", "data-brand", "Girl", "facet-count"),
    chip("facet-value", "data-brand", "NopeBrand", "facet-count"),
    chip("facet-value", "data-brand", "Vans", "facet-count")
]);
const sizeFilters = h("div", { id: "sizeFilters" }, [
    button("chip width-chip", { "data-buckets": "8.0-8.125,8.125-8.25", "aria-pressed": "false" }, [span("width-count", "0")]),
    button("chip width-chip", { "data-buckets": "8.5-8.75", "aria-pressed": "false" }, [span("width-count", "0")]),
    button("chip width-chip is-zero is-unavailable", { "data-buckets": "10up", "aria-pressed": "false" }, [span("width-count", "0")])
]);
function quick(attr, value, pressed) {
    return button("chip quick-chip" + (pressed ? " active" : ""), { [attr]: value, "aria-pressed": pressed ? "true" : "false", "data-home": "row" }, [
        span("quick-count", "0")
    ]);
}
const moreList = h("div", { id: "moreStoresList", class: "more-list" }, [
    button("chip quick-chip", { "data-store": "Tactics", "aria-pressed": "false", "data-home": "more" }, [span("quick-count", "0")]),
    button("chip quick-chip", { "data-store": "SkateWarehouse", "aria-pressed": "false", "data-home": "more" }, [span("quick-count", "0")])
]);
const moreMenu = h("div", { id: "moreStores", class: "more-menu" }, [
    button("chip more-toggle", { "aria-expanded": "false" }, [h("span", { text: "+ More stores" })]),
    moreList
]);
const storeRow = h("div", { class: "quick-row" }, [
    quick("data-store", "all", true),
    quick("data-store", "Zumiez", false),
    quick("data-store", "CCS", false),
    moreMenu
]);
const storeFilters = h("div", { id: "storeFilters" }, [storeRow]);
const partFilters = h("div", { id: "partFilters" }, [
    h("div", { class: "quick-row" }, [
        quick("data-part", "all", false),
        quick("data-part", "Decks", true),
        quick("data-part", "Wheels", false),
        quick("data-part", "Sneakers", false)
    ])
]);
const lengthSelect = select("lengthSelect", ["all", "31", "32", "33"]);
const storeSelect = select("storeSelect", ["all", "Zumiez", "CCS", "Tactics", "SkateWarehouse"]);
const partSelect = select("partSelect", ["all", "Decks", "Wheels", "Sneakers"]);
partSelect.value = "Decks";
const diameterFilters = h("div", { id: "diameterFilters" }, ["52-53", "54-55", "50-51"].map(value => (
    button("chip spec-chip", { "data-value": value, "aria-pressed": "false" }, [span("spec-count", "0")])
)));
const shoeFilters = h("div", { id: "shoesizeFilters" }, ["8", "9.5"].map(value => (
    button("chip spec-chip", { "data-value": value, "aria-pressed": "false" }, [span("spec-count", "0")])
)));
const intervals = h("div", { id: "dropInterval" }, ["all", "day"].map(value => (
    button("interval-btn", { "data-interval": value, "aria-pressed": value === "all" ? "true" : "false" }, [span("facet-count", "")])
)));
const kinds = h("div", { id: "dealTypes" }, ["new", "drop", "hot"].map(value => (
    button("kind-btn", { "data-kind": value, "aria-pressed": "false" }, [span("facet-count", "")])
)));
[table, brandList, sizeFilters, storeFilters, partFilters, lengthSelect, storeSelect, partSelect, diameterFilters, shoeFilters, intervals, kinds].forEach(node => body.appendChild(node));
/*__CHECKS__*/
function byBrand(name) {
    return brandList.querySelectorAll(".facet-value").find(node => node.getAttribute("data-brand") === name);
}
function byBuckets(id) {
    return sizeFilters.querySelectorAll(".width-chip").find(node => (node.getAttribute("data-buckets") || "").indexOf(id) >= 0);
}
function byStore(name) {
    return storeFilters.querySelectorAll(".quick-chip").find(node => node.getAttribute("data-store") === name);
}
function byPart(name) {
    return partFilters.querySelectorAll(".quick-chip").find(node => node.getAttribute("data-part") === name);
}
function spec(root, value) {
    return root.querySelectorAll(".spec-chip").find(node => node.getAttribute("data-value") === value);
}
function shown(node) { return facetShown(node); }
function paint() {
    paintBrandFacet();
    paintWidthChips();
    paintFacetCounts();
}
state.store = "Zumiez";
state.part = "Decks";
state.brand = "all";
storeSelect.value = "Zumiez";
partSelect.value = "Decks";
paint();
assert.equal(shown(byStore("CCS")), true, "same-group store stays so it can be switched to");
assert.equal(byStore("CCS").querySelector(".quick-count").textContent, "1");
assert.equal(shown(byPart("Wheels")), true, "same-group product type stays");
assert.equal(shown(byBrand("Baker")), true);
assert.equal(shown(byBrand("Girl")), false, "a brand with no Zumiez deals stays hidden");
state.store = "CCS";
state.brand = "Baker";
storeSelect.value = "CCS";
paint();
assert.equal(byBrand("Baker").getAttribute("aria-pressed"), "true");
assert.equal(byBrand("Baker").classList.contains("is-zero"), true);
assert.equal(shown(byBrand("Baker")), true, "selected brand stays at zero");
assert.equal(shown(byBrand("Girl")), true, "other brand in the group stays");
assert.equal(byBrand("Girl").querySelector(".facet-count").textContent, "(1)");
assert.equal(shown(byStore("CCS")), true, "selected store stays at zero");
assert.equal(byStore("CCS").classList.contains("is-zero"), true);
assert.equal(shown(byStore("Zumiez")), true);
assert.equal(shown(byBrand("NopeBrand")), false);
state.store = "all";
state.brand = "all";
state.widths = ["8.0-8.125", "8.125-8.25"];
storeSelect.value = "all";
paint();
assert.equal(byBuckets("8.0-8.125").getAttribute("aria-pressed"), "true");
assert.equal(shown(byBuckets("8.5-8.75")), true, "other width stays so it can be added");
assert.equal(byBuckets("8.5-8.75").querySelector(".width-count").textContent, "1");
assert.equal(shown(byBuckets("10up")), false, "zero width is hidden");
state.widths = [];
state.part = "Wheels";
state.diameters = ["52-53"];
partSelect.value = "Wheels";
paint();
assert.equal(shown(spec(diameterFilters, "52-53")), true);
assert.equal(spec(diameterFilters, "52-53").getAttribute("aria-pressed"), "true");
assert.equal(shown(spec(diameterFilters, "54-55")), true, "same-group diameter stays");
assert.equal(spec(diameterFilters, "54-55").querySelector(".spec-count").textContent, "1");
assert.equal(shown(spec(diameterFilters, "50-51")), false);
state.part = "Sneakers";
state.diameters = [];
partSelect.value = "Sneakers";
paint();
assert.equal(spec(shoeFilters, "8").querySelector(".spec-count").textContent, "1");
assert.equal(shown(spec(shoeFilters, "8")), true);
assert.equal(shown(spec(shoeFilters, "9.5")), false, "named size that is not in stock stays hidden");
state.part = "Decks";
state.brand = "all";
state.store = "all";
partSelect.value = "Decks";
lengthSelect.value = "all";
paint();
assert.equal(lengthSelect.options.some(option => option.value === "33"), false, "zero length is removed");
assert.equal(lengthSelect.options.some(option => option.value === "31"), true);
assert.equal(lengthSelect.options.some(option => option.value === "32"), true);
state.length = "33";
lengthSelect.value = "33";
paint();
const kept = lengthSelect.options.find(option => option.value === "33");
assert.ok(kept, "selected length stays at zero");
assert.equal(kept.disabled, false);
assert.equal(lengthSelect.options.some(option => option.value === "31"), true, "same-group lengths stay");
state.length = "all";
lengthSelect.value = "all";
paint();
const day = intervals.querySelector('[data-interval="day"]');
const allInterval = intervals.querySelector('[data-interval="all"]');
assert.equal(shown(day), false);
assert.equal(shown(allInterval), true);
assert.equal(shown(kinds.querySelector('[data-kind="hot"]')), false);
assert.equal(shown(kinds.querySelector('[data-kind="new"]')), true);
state.kinds = ["hot"];
paint();
assert.equal(shown(kinds.querySelector('[data-kind="hot"]')), true, "selected deal type stays at zero");
assert.equal(shown(kinds.querySelector('[data-kind="drop"]')), true, "same-group deal type stays");
state.kinds = [];
state.search = "no-such-deck";
paint();
const note = sizeFilters.querySelector(".filter-empty");
assert.ok(note && facetShown(note), "empty width group shows a note");
assert.equal(note.textContent, "No sizes match");
state.search = "";
paint();
assert.equal(facetShown(sizeFilters.querySelector(".filter-empty")), false);
filterBrandList("girl");
assert.equal(byBrand("Girl").classList.contains("is-search-hide"), false);
assert.equal(shown(byBrand("Girl")), true);
assert.equal(byBrand("Baker").classList.contains("is-search-hide"), true);
filterBrandList("nope");
assert.equal(shown(byBrand("NopeBrand")), false, "search does not reveal a zero brand");
const emptyBrands = brandList.querySelector(".filter-empty");
assert.ok(emptyBrands && facetShown(emptyBrands));
filterBrandList("");
assert.equal(shown(byBrand("Baker")), true);
assert.equal(facetShown(brandList.querySelector(".filter-empty")), false);
state.part = "Decks";
partSelect.value = "Decks";
paint();
syncNavMore(navClusters()[0]);
assert.equal(moreMenu.hidden, true, "show-more hides when every extra store is zero");
state.part = "all";
partSelect.value = "all";
paint();
syncNavMore(navClusters()[0]);
assert.equal(shown(byStore("Tactics")), true);
assert.equal(shown(byStore("SkateWarehouse")), false);
assert.equal(moreMenu.hidden, false, "show-more stays when a visible extra remains");
"""
        preamble, checks = script.split("/*__CHECKS__*/", 1)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
            handle.write(preamble)
            handle.write("\n")
            handle.write(source)
            handle.write("\n")
            handle.write(checks)
            path = handle.name
        result = subprocess.run(["node", path], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
