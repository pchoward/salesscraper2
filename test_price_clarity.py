"""Price confidence on deal cards and in the quick view.

The percent off a store's list price is a claimed discount. Tracked history is
separate, and a short history stays labeled as short.
"""

import subprocess
import unittest
from pathlib import Path

from report import build_report_html


def _deck(price, url, store, name, old="80.00"):
    return {
        "name": name,
        "url": url,
        "price_new": price,
        "price_old": old,
        "part": "Decks",
        "store": store,
        "image": "https://example.com/deck.jpg",
    }


def _cards(html):
    return [
        part.split("</article>", 1)[0]
        for part in html.split('<article class="deal-card')[1:]
    ]


class CardPriceClarityTests(unittest.TestCase):
    def test_claimed_discount_sits_beside_the_price_not_on_the_photo(self):
        deck = _deck("39.99", "https://example.com/deck", "Zumiez", "Baker Logo Deck")
        hardware = {
            "name": "Independent Bolts",
            "url": "https://example.com/bolts",
            "price_new": "3.95",
            "price_old": None,
            "part": "Bearings",
            "store": "Zumiez",
            "image": "https://example.com/bolts.jpg",
        }
        html = build_report_html(
            {"Zumiez_Decks": [deck], "Zumiez_Bearings": [hardware]},
            {},
            generated_at="2026-10-18T19:12:00+00:00",
        )
        cards = _cards(html)
        deck_card = next(card for card in cards if "Baker Logo" in card)
        bare_card = next(card for card in cards if "Independent Bolts" in card)
        for card in (deck_card, bare_card):
            media = card.split('<div class="media">', 1)[1].split('<div class="card-face">', 1)[0]
            prices = card.split('<div class="card-prices">', 1)[1].split("</div>", 1)[0]
            self.assertIn('class="hero', media)
            self.assertNotIn("card-off", media)
            self.assertNotIn("vs list", media)
            self.assertIn("card-off", prices)
            self.assertIn(">Details</button>", card)
            self.assertNotIn("You save", card)

        prices = deck_card.split('<div class="card-prices">', 1)[1].split("</div>", 1)[0]
        self.assertIn("50% vs list", prices)
        self.assertIn("not a tracked market price", prices)
        self.assertIn("Now:", prices)
        bare_prices = bare_card.split('<div class="card-prices">', 1)[1].split("</div>", 1)[0]
        self.assertIn("No discount info", bare_prices)
        self.assertIn("no claimed discount", bare_prices)
        self.assertNotIn("vs list", bare_prices)

    def test_claimed_chip_is_neutral_and_history_lines_fit_a_phone(self):
        css = Path("page.css").read_text(encoding="utf-8")
        mobile = Path("mobile.css").read_text(encoding="utf-8")
        chip = css.split(".deal-card .card-off.high,", 1)[1].split("}", 1)[0]
        self.assertIn("#f1f5f9", chip)
        self.assertIn("#334155", chip)
        self.assertNotIn("#dcfce7", chip)
        badge = css.split(".quick-discount {", 1)[1].split("}", 1)[0]
        self.assertIn("#f1f5f9", badge)
        self.assertNotIn("#dcfce7", badge)
        self.assertIn(".quick-history", css)
        self.assertIn(".quick-also", css)
        self.assertIn(".quick-price-note", css)
        self.assertIn("#quickView .quick-history", mobile)
        self.assertIn("#quickView .quick-also", mobile)


class QuickViewPriceClarityTests(unittest.TestCase):
    def test_history_claims_and_other_stores_stay_distinct(self):
        source = Path("page.js").read_text(encoding="utf-8")
        add_days = source[source.index("function addDays("):source.index("function markerColor(")]
        facts = source[source.index("function quickClip("):source.index("function quickGalleryImages(")]
        gallery = source[source.index("function quickGalleryImages("):source.index("function syncQuickStar(")]
        rendering = source[source.index("function fillQuickView("):source.index("function quickTopLimit(")]
        offers = source[source.index("function specTokens("):source.index("function specAllowed(")]
        script = r'''
const assert = require('node:assert/strict');
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
class Element {
    constructor(tag = 'div') {
        this.tag = tag; this.children = []; this.style = {}; this.attrs = {}; this.className = '';
        this.events = {}; this.dataset = {}; this._text = ''; this.hidden = false; this.title = '';
    }
    append(...nodes) { this.children.push(...nodes); }
    appendChild(node) { this.append(node); }
    replaceChildren(...nodes) { this.children = nodes; }
    setAttribute(name, value) { this.attrs[name] = String(value); if (name === 'class') this.className = String(value); }
    getAttribute(name) { return this.attrs[name] || null; }
    removeAttribute(name) { delete this.attrs[name]; }
    addEventListener(name, callback) { this.events[name] = callback; }
    cloneNode(deep) {
        const copy = new Element(this.tag);
        copy.className = this.className; copy._text = this._text;
        if (deep) copy.children = this.children.map(child => child.cloneNode(true));
        return copy;
    }
    matches(selector) {
        if (selector.includes(',')) return selector.split(',').some(part => this.matches(part.trim()));
        const step = selector.split(/\s+/).filter(Boolean)[0] || '';
        if (step.startsWith('.')) return step.split('.').filter(Boolean).every(name => this.className.split(/\s+/).includes(name));
        return this.tag === step;
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    querySelectorAll(selector) {
        const steps = selector.split(/\s+/).filter(Boolean);
        let nodes = this.children.flatMap(child => [child, ...child.querySelectorAll('*')]);
        if (selector === '*') return nodes;
        steps.forEach((step, index) => {
            if (index === 0) nodes = nodes.filter(node => node.matches(step));
            else nodes = nodes.flatMap(node => node.querySelectorAll(step));
        });
        return nodes;
    }
    get textContent() { return this.children.length ? this.children.map(child => child.textContent).join('') : this._text; }
    set textContent(value) { this._text = String(value); this.children = []; }
    get classList() {
        const el = this;
        return {
            contains: name => el.className.split(/\s+/).includes(name),
            add: name => { if (!el.className.split(/\s+/).includes(name)) el.className = (el.className + ' ' + name).trim(); },
            remove: name => { el.className = el.className.split(/\s+/).filter(bit => bit && bit !== name).join(' '); }
        };
    }
}
const body = new Element();
const panel = new Element();
panel.append(Object.assign(new Element(), {className: 'quick-panel'}));
const document = {
    getElementById: id => ({quickView: panel, quickBody: body}[id]),
    createElement: tag => new Element(tag),
    createElementNS: (ns, tag) => new Element(tag),
    querySelectorAll: selector => body.querySelectorAll(selector)
};
const window = {innerWidth: 1200, innerHeight: 900};
function syncQuickStar() {}
function closeQuickView() {}
const state = {shoeSizes: []};
'''
        script += add_days + facts + gallery + rendering + offers + r'''
assert.equal(quickHistoryNote({symbol:'$', points:[]}), 'No tracked price history yet.');
assert.equal(
    quickHistoryNote({symbol:'$', points:[['2026-10-17', 40]]}),
    'Only one tracked price ($40.00 on Oct 17). Not enough history to compare.'
);
assert.equal(
    quickHistoryNote({
        symbol:'$',
        points:[['2026-09-01', 70], ['2026-10-01', 55], ['2026-10-17', 59.5]],
        atl:{price:55, date:'2026-10-01'}
    }),
    'Tracked low $55.00 on Oct 1 · 3 tracked prices.'
);
assert.equal(
    quickHistoryNote({symbol:'$', points:[['2026-09-01', 70], ['2026-10-17', 59.5]]}),
    'Previous tracked price $70.00 on Sep 1 · 2 tracked prices.'
);
assert.equal(quickHistoryNote({symbol:'$', points:[['2026-10-17', 40]]}).includes('Tracked low'), false);
assert.equal(quickPercent('30'), '30% vs list');
assert.equal(quickPercent('0'), '');
assert.equal(quickPercent(''), '');

const claimed = quickFacts(
    {price:'59.50', original:'85', discount:'30', days:'18', daysat:'4'},
    {url:'https://example.com/shoe', store:'CCS', first:'2026-09-01',
     daily:[['2026-09-01', 70], ['2026-10-01', 55], ['2026-10-17', 59.5]],
     seriesList:[{url:'https://example.com/shoe', low:{date:'2026-10-01', price:55}, points:[], markers:[]}]},
    '2026-10-17'
);
const labels = claimed.rows.map(row => row.label + '=' + row.value).join(' | ');
assert.equal(labels.includes('You save'), false);
assert.equal(labels.includes('Claimed discount=30% vs list'), true);
assert.equal(labels.includes('List price=$85.00'), true);
assert.equal(labels.includes('All-time low=$55.00 on Oct 1'), true);
const listAt = claimed.rows.findIndex(row => row.label === 'List price');
const lowAt = claimed.rows.findIndex(row => row.label === 'All-time low');
assert.equal(listAt >= 0 && lowAt > listAt, true);

const none = quickCompare(
    {price:'40', original:'', days:'0'},
    {symbol:'$', points:[], average:null, atl:null}
);
assert.equal(none.find(cell => cell.label === 'Average').value, 'No history');
assert.equal(none.find(cell => cell.label === 'Lowest').value, 'No history');
assert.match(none.find(cell => cell.label === 'List price').hint, /not a tracked market price/);
assert.match(none.find(cell => cell.label === 'Lowest').hint, /No tracked low yet/);
const one = quickCompare(
    {price:'40', original:'80', days:'40'},
    {symbol:'$', points:[['2026-10-17', 40]], average:40, atl:null}
);
assert.equal(one.find(cell => cell.label === 'Average').value, '$40.00');
assert.match(one.find(cell => cell.label === 'Average').hint, /Only one tracked price/);
assert.equal(one.find(cell => cell.label === 'Lowest').value, 'No history');

const also = quickAlsoLine({
    url:'https://example.com/shoe',
    offers:[
        {store:'CCS', url:'https://example.com/shoe', price:59.5, currency:'USD'},
        {store:'Tactics', url:'https://example.com/tactics', price:64, currency:'USD'},
        {store:'Warehouse', url:'https://example.com/wh', price:50, currency:'USD'}
    ]
});
assert.equal(also, 'Also at Tactics $64.00 · Cheaper at Warehouse $50.00');
assert.equal(also.includes('lowest'), false);

const shoe = {
    name:'Nike SB Dunk', store:'CCS', url:'https://example.com/shoe', first:'2026-09-01',
    image:'https://example.com/front.jpg', images:[],
    daily:[['2026-09-01', 70], ['2026-10-01', 55], ['2026-10-17', 59.5]],
    seriesList:[{url:'https://example.com/shoe', low:{date:'2026-10-01', price:55}, markers:[]}],
    offers:[
        {store:'CCS', url:'https://example.com/shoe', price:59.5, currency:'USD', cheapest:true, availability:'On sale'},
        {store:'Tactics', url:'https://example.com/tactics', price:64, currency:'USD', cheapest:false, availability:'On sale'}
    ]
};
let catalog = () => ({items:{shoe:shoe}, generated:'2026-10-17'});
const card = new Element('article');
card.dataset = {id:'shoe', price:'59.50', original:'85', discount:'30', days:'40', daysat:'1', store:'CCS'};
card.className = 'deal-card';
const since = new Element('p');
since.className = 'price-since';
since.textContent = 'Dropped from $70.00 on Oct 17';
card.appendChild(since);
fillQuickView(card);
const badge = body.querySelector('.quick-discount');
assert.equal(badge.textContent, '30% vs list');
assert.match(badge.title, /claimed discount/);
assert.match(body.querySelector('.quick-list').textContent, /List price/);
assert.match(body.querySelector('.is-original').title, /not a tracked market price/);
const history = body.querySelector('.quick-history');
assert.equal(history.textContent, 'Tracked low $55.00 on Oct 1 · 90-day average $61.50 · 3 tracked prices.');
assert.equal(body.querySelector('.quick-also').textContent, 'Also at Tactics $64.00');
const more = body.querySelector('.quick-more');
assert.equal(more.tag, 'details');
assert.ok(!more.attrs.open);
assert.equal(more.querySelector('.quick-history'), history);
assert.equal(more.querySelector('.quick-also').textContent, 'Also at Tactics $64.00');
assert.equal(body.querySelector('.quick-product').querySelector('.quick-history'), null);
assert.equal(body.querySelector('.quick-product').querySelector('.quick-also'), null);
assert.match(more.querySelector('.quick-price-note').textContent, /not a tracked market price/);
assert.ok(more.querySelector('.quick-compare'));
assert.ok(more.querySelector('.quick-stores'));
assert.match(more.querySelector('.quick-stores').textContent, /cheapest listed/);
assert.equal(more.querySelector('.quick-stores').textContent.includes('lowest'), false);
assert.equal(body.textContent.includes('You save'), false);

const emptyCard = new Element('article');
emptyCard.dataset = {id:'none', price:'40', original:'', discount:'', days:'0', daysat:'0'};
const emptyItem = {name:'Bare', store:'CCS', url:'https://example.com/bare', image:'', images:[], daily:[], offers:[]};
catalog = () => ({items:{none:emptyItem}, generated:'2026-10-17'});
fillQuickView(emptyCard);
assert.equal(body.querySelector('.quick-discount'), null);
assert.equal(body.querySelector('.quick-history').textContent, 'No tracked price history yet.');
assert.equal(body.querySelector('.quick-also'), null);
const emptyCompare = body.querySelectorAll('.quick-compare strong').map(node => node.textContent);
assert.equal(emptyCompare.includes('No history'), true);
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_size_price_keeps_the_claimed_label(self):
        source = Path("page.js").read_text(encoding="utf-8")
        chunk = source[source.index("function specTokens("):source.index("function specAllowed(")]
        script = r'''
const assert = require('node:assert/strict');
class Element {
    constructor(tag) {
        this.tag = tag; this.children = []; this.className = ''; this.dataset = {}; this._text = ''; this.title = '';
    }
    appendChild(node) { this.children.push(node); }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    querySelectorAll(selector) {
        const want = selector.split(',').map(part => part.trim());
        const all = this.children.flatMap(child => [child, ...child.querySelectorAll(selector)]);
        return all.filter(node => want.some(part => {
            if (!part.startsWith('.')) return node.tag === part;
            return part.slice(1).split('.').every(name => node.className.split(/\s+/).includes(name));
        }));
    }
    get textContent() { return this.children.length ? this.children.map(child => child.textContent).join('') : this._text; }
    set textContent(value) { this._text = String(value); this.children = []; }
    get classList() {
        const el = this;
        return {
            contains: name => el.className.split(/\s+/).includes(name),
            add: name => { if (!el.className.split(/\s+/).includes(name)) el.className = (el.className + ' ' + name).trim(); },
            remove: name => { el.className = el.className.split(/\s+/).filter(bit => bit && bit !== name).join(' '); }
        };
    }
}
const card = new Element('article');
card.className = 'deal-card';
card.dataset = {
    part:'Sneakers', price:'70.00', discount:'30', original:'100',
    shoeprices:'8:60,9:80', shoecompares:'8:100,9:100', shoesize:'8,9', priceSaved:''
};
const now = new Element('span');
now.className = 'now-price';
now.textContent = 'Now: $70.00';
const off = new Element('span');
off.className = 'discount card-off medium';
off.textContent = '30% vs list';
off.title = "Store's claimed discount versus its list price, not a tracked market price.";
card.appendChild(now);
card.appendChild(off);
const document = {querySelectorAll: () => [card]};
const state = {shoeSizes: ['9']};
''' + chunk + r'''
paintOfferPrices();
assert.equal(off.textContent, '20% vs list');
assert.match(off.title, /claimed discount/);
assert.equal(off.className.split(/\s+/).includes('low'), true);
state.shoeSizes = [];
paintOfferPrices();
assert.equal(off.textContent, '30% vs list');
assert.match(off.title, /not a tracked market price/);
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
