"""Quick-view gallery rendering and placement regressions using Node."""

import subprocess
import unittest
from pathlib import Path


class QuickViewTests(unittest.TestCase):
    def test_compact_quick_view_styles(self):
        css = Path(__file__).with_name("page.css").read_text(encoding="utf-8")
        mobile = Path(__file__).with_name("mobile.css").read_text(encoding="utf-8")
        page = Path(__file__).with_name("page.py").read_text(encoding="utf-8")
        frame = css.split(".quick-image-frame {", 1)[1].split("}", 1)[0]
        self.assertIn("height: 190px", frame)
        self.assertIn("object-fit: cover", css[css.index(".quick-image-frame img"):css.index(".quick-image-frame img") + 280])
        self.assertIn(".quick-more > summary", css)
        self.assertIn(".quick-list", css)
        self.assertIn(".quick-badge", css)
        self.assertIn(".quick-specs-table", css)
        self.assertIn(".quick-product { display: grid; grid-template-columns: auto minmax(0, 1fr);", css)
        self.assertIn(".deal-card:hover .card-quick", css)
        self.assertIn(".deal-card:focus-within .card-quick", css)
        self.assertIn("(hover: hover) and (pointer: fine)", css)
        media = page.split('<div class="media">', 1)[1].split("card-sparkline", 1)[0]
        self.assertIn('class="card-quick"', media)
        self.assertIn(">Quick view</button>", media)
        script = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        handler = script[script.index('closest(".card-quick")'):script.index('closest(".card-quick")') + 420]
        self.assertIn("openQuickView(card, true)", handler)
        closer = script[script.index("function wireQuickView("):script.index("function placeScoreFloat(")]
        self.assertIn(".card-quick", closer)
        product = mobile[mobile.index("#quickView .quick-product"):]
        self.assertIn("grid-template-columns: minmax(0, 1fr)", product)
        self.assertIn("min-height: 180px", mobile)
        self.assertIn("#quickView .quick-more > summary", mobile)
        self.assertIn("min-height: 2.75rem", mobile[mobile.index("#quickView .quick-more > summary"):])

    def test_gallery_content_navigation_and_viewport_placement(self):
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        gallery = source[source.index("function quickGalleryImages("):source.index("function syncQuickStar(")]
        rendering = source[source.index("function fillQuickView("):source.index("function quickTopLimit(")]
        placement = source[source.index("function quickTopLimit("):source.index("function closeQuickView(")]
        script = r'''
const assert = require('node:assert/strict');
class Element {
    constructor(tag = 'div') { this.tag = tag; this.children = []; this.style = {}; this.attrs = {}; this.className = ''; this.events = {}; }
    append(...nodes) { this.children.push(...nodes); }
    appendChild(node) { this.append(node); }
    replaceChildren(...nodes) { this.children = nodes; }
    setAttribute(name, value) { this.attrs[name] = value; }
    getAttribute(name) { return this.attrs[name] || null; }
    addEventListener(name, callback) { this.events[name] = callback; }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    querySelectorAll(selector) {
        const matches = n => selector.startsWith('.') ? n.className.split(' ').includes(selector.slice(1)) : n.tag === selector;
        return this.children.flatMap(n => [...(matches(n) ? [n] : []), ...n.querySelectorAll(selector)]);
    }
    get classList() { return {contains: c => this.className.split(' ').includes(c), add: c => { this.className += ' ' + c; }}; }
    getBoundingClientRect() { return {height: this.naturalHeight || 430}; }
}
const body = new Element();
const dialog = new Element(); dialog.className = 'quick-panel';
const panel = new Element(); panel.append(dialog);
const document = {
    getElementById: id => ({quickView: panel, quickBody: body, stickyBar: {getBoundingClientRect: () => ({bottom: 100})}}[id]),
    createElement: tag => new Element(tag), body: new Element()
};
const window = {innerWidth: 1200, innerHeight: 900};
const item = {name: 'Nike SB Dunk Low Pro', store: 'CCS', image: 'https://example.com/front.jpg',
    images: ['https://example.com/front.jpg', 'https://example.com/back.jpg', 'javascript:alert(1)', 'https://example.com/back.jpg']};
const catalog = () => ({items: {shoe: item}, generated: '2026-10-18'});
const facts = {specs: [{label: 'In stock', value: '6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10, 10.5, 11'}], symbol: '$', viewUrl: 'https://example.com/product', viewLabel:'View at CCS'};
const quickFacts = () => facts;
const quickMoney = (symbol, price) => symbol + Number(price).toFixed(2);
const quickPercent = () => '30% off';
const syncQuickStar = () => {};
const image = new Element('img'); image.attrs.src = item.image;
let anchor = {left: 1000, right: 1190, top: 780, bottom: 880, width: 190, height: 100};
const card = {dataset: {id: 'shoe', price: '70'}, querySelector: () => image, getBoundingClientRect: () => anchor};
const closeQuickView = () => { throw new Error('Unexpected close'); };
'''
        script += gallery + rendering + placement + r'''
assert.deepEqual(quickGalleryImages(item, card), ['https://example.com/front.jpg', 'https://example.com/back.jpg']);
fillQuickView(card);
assert.equal(body.querySelector('.quick-title').textContent, item.name);
assert.equal(body.querySelector('.quick-head').querySelector('.quick-title'), null, 'title sits in the right column');
assert.equal(body.querySelector('.quick-identity').querySelector('.quick-title').textContent, item.name);
assert.equal(body.querySelector('.quick-kicker').textContent, 'CCS');
assert.equal(body.querySelector('.quick-price').children[0].textContent, '$70.00');
assert.equal(body.querySelector('.quick-close').attrs['aria-label'], 'Close quick view');
assert.equal(body.querySelectorAll('.quick-spec-chip').length, 10);
assert.equal(body.querySelectorAll('.quick-spec-chip').at(-1).textContent, '11');
const more = body.querySelector('.quick-more');
assert.equal(more.tag, 'details');
assert.ok(!more.attrs.open, 'more details starts collapsed');
assert.equal(more.querySelector('summary').textContent, 'More details');
assert.equal(more.querySelectorAll('.quick-spec-chip').length, 10, 'full sizes sit behind more details');
assert.equal(body.querySelector('.quick-specs-table'), null, 'a size list is not a key spec');
assert.equal(body.querySelector('.quick-product').children[0].className, 'quick-gallery');
assert.equal(more.querySelector('.quick-view-link'), null);
assert.equal(body.querySelector('.quick-view-link').textContent, 'View at CCS');
for (const c of ['quick-chart','quick-tracking','quick-facts','quick-score','quick-stores']) assert.equal(body.querySelector('.'+c), null);
const controls = body.querySelector('.quick-gallery-controls');
const photo = body.querySelector('.quick-gallery').querySelector('img');
assert.equal(photo.src, item.image);
assert.equal(controls.children[1].textContent, '1 / 2');
controls.children[2].events.click();
assert.equal(photo.src, item.images[1]);
assert.equal(controls.children[1].textContent, '2 / 2');
controls.children[2].events.click(); assert.equal(photo.src, item.image, 'wrap forward');
controls.children[0].events.click(); assert.equal(photo.src, item.images[1], 'wrap backward');
body.querySelector('.quick-gallery').events.keydown({key:'ArrowRight',preventDefault(){}});
assert.equal(photo.src, item.image, 'keyboard navigation');
photo.events.error(); assert.ok(photo.hidden); assert.equal(body.querySelector('.quick-image-missing').hidden, false);
controls.children[2].events.click(); assert.equal(photo.hidden, false, 'next image recovers after error');
const frame=body.querySelector('.quick-image-frame');
frame.events.touchstart({touches:[{clientX:150,clientY:100}]});
frame.events.touchend({changedTouches:[{clientX:20,clientY:105}]});
assert.equal(photo.src,item.image,'horizontal swipe navigates');
frame.events.touchstart({touches:[{clientX:150,clientY:100}]});
frame.events.touchend({changedTouches:[{clientX:100,clientY:300}]});
assert.equal(photo.src,item.image,'vertical scroll does not navigate');
item.images = []; fillQuickView(card);
assert.equal(body.querySelector('.quick-gallery-controls'),null,'no controls for one photo');
item.image='';image.attrs.src=''; fillQuickView(card);
assert.equal(body.querySelector('img').hidden,true);
assert.equal(body.querySelector('.quick-image-missing').hidden,false,'missing photo fallback');
placeQuickView(card);
assert.equal(panel.style.width, '460px');
assert.equal(panel.style.height, 'auto');
assert.equal(panel.style.left, '730px', 'flip left at right edge');
assert.equal(panel.style.top, '462px', 'flip upward at bottom edge');
anchor = {...anchor, left: -30, right: 160, top: 0};
placeQuickView(card);
assert.equal(panel.style.left, '8px');
assert.equal(panel.style.top, '104px', 'keep clear of navigation');
panel.naturalHeight = 850; placeQuickView(card);
assert.ok(panel.classList.contains('is-sheet'));
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_price_context_score_chart_and_offers(self):
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        add_days = source[source.index("function addDays("):source.index("function markerColor(")]
        facts = source[source.index("function quickClip("):source.index("function quickGalleryImages(")]
        gallery = source[source.index("function quickGalleryImages("):source.index("function syncQuickStar(")]
        nearest = source[source.index("function nearestChartHit("):source.index("const FILTER_SECTION_KEY")]
        rendering = source[source.index("function fillQuickView("):source.index("function quickTopLimit(")]
        script = r'''
const assert = require('node:assert/strict');
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
class Element {
    constructor(tag = 'div') {
        this.tag = tag; this.children = []; this.style = {}; this.attrs = {}; this.className = '';
        this.events = {}; this.dataset = {}; this._text = '';
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
        copy.className = this.className; copy.attrs = Object.assign({}, this.attrs); copy._text = this._text;
        if (deep) copy.children = this.children.map(child => child.cloneNode(true));
        return copy;
    }
    matches(selector) {
        if (selector.includes(',')) return selector.split(',').some(part => this.matches(part.trim()));
        const steps = selector.split(/\s+/).filter(Boolean);
        if (steps.length !== 1) return false;
        const step = steps[0];
        if (step.startsWith('.')) return step.split('.').filter(Boolean).every(name => this.className.split(/\s+/).includes(name));
        return this.tag === step;
    }
    querySelector(selector) {
        if (selector.includes(',')) {
            for (const part of selector.split(',')) {
                const found = this.querySelector(part.trim());
                if (found) return found;
            }
            return null;
        }
        return this.querySelectorAll(selector)[0] || null;
    }
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
    get classList() { return {contains: name => this.className.split(/\s+/).includes(name)}; }
    getBoundingClientRect() { return {left: 0, top: 0, width: 500, height: 144, right: 500, bottom: 144}; }
}
const body = new Element();
const panel = new Element();
panel.append(Object.assign(new Element(), {className: 'quick-panel'}));
const document = {
    getElementById: id => ({quickView: panel, quickBody: body}[id]),
    createElement: tag => new Element(tag),
    createElementNS: (ns, tag) => new Element(tag)
};
const window = {innerWidth: 1200, innerHeight: 900};
function syncQuickStar() {}
function closeQuickView() {}
'''
        script += add_days + facts + gallery + nearest + rendering + r'''
function factor(label, points, note) {
    const li = document.createElement('li');
    if (note) li.className = 'why-note';
    const span = document.createElement('span');
    span.textContent = label;
    const score = document.createElement('b');
    score.textContent = points;
    li.append(span, score);
    return li;
}
function whyBlock() {
    const why = document.createElement('div');
    why.className = 'why';
    why.attrs.id = 'why-card-shoe';
    const strong = document.createElement('strong');
    strong.textContent = 'Why 65?';
    const list = document.createElement('ul');
    list.append(
        factor('Discount', '+40'),
        factor('Historical low', '+25'),
        factor('Recent drop', '+0'),
        factor('Popular size', '+0'),
        factor('Tracked 40 days', 'not scored', true)
    );
    const legend = document.createElement('p');
    legend.className = 'why-legend';
    legend.textContent = 'Days tracked are not added.';
    why.append(strong, list, legend);
    const wrap = document.createElement('div');
    wrap.className = 'card-score';
    wrap.appendChild(why);
    return wrap;
}
function cardFor(id, dataset, since, lowClass, lowText) {
    const card = document.createElement('article');
    card.dataset = Object.assign({id: id, store: 'CCS'}, dataset);
    const line = document.createElement('p');
    line.className = 'price-since';
    line.textContent = since;
    card.appendChild(line);
    if (lowClass) {
        const low = document.createElement('span');
        low.className = lowClass;
        low.textContent = lowText;
        card.appendChild(low);
    }
    card.appendChild(whyBlock());
    const wrap = document.createElement('div');
    wrap.className = 'hero-wrap';
    const image = document.createElement('img');
    image.attrs.src = 'https://example.com/front.jpg';
    wrap.appendChild(image);
    card.appendChild(wrap);
    return card;
}
const shoe = {
    name: 'Nike SB Dunk', store: 'CCS', url: 'https://example.com/shoe', first: '2026-09-01',
    image: 'https://example.com/front.jpg', images: ['https://example.com/front.jpg', 'https://example.com/side.jpg'],
    daily: [['2026-09-01', 70], ['2026-10-01', 55], ['2026-10-17', 59.5]],
    seriesList: [{
        url: 'https://example.com/shoe',
        low: {date: '2026-10-01', price: 55},
        markers: [{date: '2026-10-17', kind: 'drop', price: 59.5, label: 'Price reduction'}]
    }],
    offers: [
        {store: 'CCS', url: 'https://example.com/shoe', price: 59.5, currency: 'USD', cheapest: true, availability: 'On sale'},
        {store: 'Tactics', url: 'https://example.com/tactics', price: 64, currency: 'USD', cheapest: false, availability: 'On sale'}
    ]
};
const heldItem = {
    name: 'Held deck', store: 'Zumiez', url: 'https://example.com/held', first: '2026-09-01',
    image: 'https://example.com/held.jpg', images: [],
    daily: [['2026-10-17', 40]],
    offers: [{store: 'Zumiez', url: 'https://example.com/held', price: 40, availability: 'On sale'}]
};
const catalog = () => ({items: {shoe: shoe, held: heldItem}, generated: '2026-10-17'});
const dropCard = cardFor('shoe', {
    price: '59.50', original: '85', discount: '30', days: '40', daysat: '1', score: '65', hot: '1',
    drop: '1', lowest: '1', hitlow: '1', fresh: '0',
    size: '8.12', length: '31.75', construction: '7-Ply Maple', brand: 'Anti Hero'
}, 'Dropped from $70.00 on Oct 17', 'pill-newlow', 'New low');
fillQuickView(dropCard);
assert.equal(body.querySelector('.quick-title').textContent, 'Nike SB Dunk');
assert.equal(body.querySelector('.quick-head').querySelector('.quick-title'), null);
assert.equal(body.querySelector('.quick-identity').querySelector('.quick-title').textContent, 'Nike SB Dunk');
assert.equal(body.querySelector('.quick-kicker').textContent, 'CCS · Anti Hero');
assert.equal(body.querySelector('.quick-gallery-controls').children[1].textContent, '1 / 2');
assert.equal(body.querySelector('.quick-product').children[0].className, 'quick-gallery');
const specs = body.querySelector('.quick-specs-table');
assert.equal(specs.querySelector('caption').textContent, 'Key specs');
assert.deepEqual(specs.querySelectorAll('th').map(node => node.textContent), ['Width', 'Length', 'Construction']);
assert.deepEqual(specs.querySelectorAll('td').map(node => node.textContent), ['8.12"', '31.75"', '7-Ply Maple']);
assert.equal(body.querySelectorAll('.quick-badge').length, 1);
assert.equal(body.querySelector('.quick-badge').textContent, 'All-time low');
assert.deepEqual(body.querySelectorAll('.quick-compare span').map(node => node.textContent), ['Now','List price','Average','Lowest','Tracked']);
assert.deepEqual(body.querySelectorAll('.quick-compare strong').map(node => node.textContent), ['$59.50','$85.00','$61.50','$55.00','40 days']);
const signal = body.querySelector('.quick-signal');
assert.ok(signal.matches('.is-drop'));
assert.equal(signal.querySelector('strong').textContent, 'New price reduction');
assert.match(signal.textContent, /New low/);
assert.equal(body.querySelector('.quick-product').querySelector('.quick-signal'), null);
assert.equal(body.querySelector('.is-held'), null);
const score = body.querySelector('.quick-score');
assert.equal(score.tag, 'details');
assert.ok(score.matches('.is-hot'));
assert.equal(score.querySelector('summary').textContent, 'Deal score 65 of 100, hot');
assert.ok(!score.attrs.open);
assert.deepEqual(score.querySelectorAll('b').map(node => node.textContent), ['+40','+25','+0','+0','not scored']);
const offers = body.querySelectorAll('.quick-stores li');
assert.equal(offers.length, 2);
assert.equal(offers[0].textContent, 'CCS $59.50On sale · cheapest listed');
assert.ok(offers[0].matches('.cheapest'));
assert.equal(offers[1].querySelector('a').href, 'https://example.com/tactics');
const chart = body.querySelector('.history-chart');
assert.match(chart.attrs['aria-label'], /Hover or tap/);
assert.equal(body.querySelector('.quick-readout').textContent, 'Oct 17, 2026 · $59.50');
chart.events.mousemove({clientX: 488, clientY: 70});
assert.match(body.querySelector('.quick-readout').textContent, /^Price reduction/);
chart.events.touchstart({touches: [{clientX: 40, clientY: 40}]});
assert.match(body.querySelector('.quick-readout').textContent, /Sep 1, 2026 · \$70\.00/);
assert.equal(body.querySelector('.quick-view-link').textContent, 'View at CCS');
const more = body.querySelector('.quick-more');
assert.equal(more.tag, 'details');
assert.ok(!more.attrs.open, 'more details starts collapsed');
assert.equal(more.querySelector('summary').textContent, 'More details');
assert.ok(more.querySelector('.quick-compare'), 'price comparison stays behind more details');
assert.ok(more.querySelector('.history-chart'));
assert.ok(more.querySelector('.quick-score'));
assert.ok(more.querySelector('.quick-stores'));
assert.ok(more.querySelector('.quick-signal'), 'the long price note stays behind more details');
assert.equal(more.querySelector('.quick-specs-table'), null);
assert.equal(more.querySelector('.quick-gallery'), null);
assert.equal(more.querySelector('.quick-view-link'), null);
assert.equal(more.querySelector('.quick-star'), null);
assert.equal(more.querySelector('.quick-badge'), null);
const list = body.querySelector('.quick-list');
assert.match(list.textContent, /List price/);
assert.match(list.textContent, /\$85\.00/);
assert.equal(list.textContent.includes('All-time low'), false);
assert.equal(list.textContent.includes('90-day'), false);
assert.ok(list.querySelector('.is-original'));
const history = more.querySelector('.quick-history');
assert.match(history.textContent, /Tracked low/);
assert.match(history.textContent, /\$55\.00/);
assert.match(history.textContent, /Oct 1/);
assert.match(history.textContent, /90-day average/);
assert.match(history.textContent, /\$61\.50/);
const meta = more.querySelector('.quick-history-meta');
assert.match(meta.textContent, /First seen/);
assert.match(meta.textContent, /Sep 1/);
assert.match(meta.textContent, /At this price/);
assert.match(meta.textContent, /1 day/);
const heldCard = cardFor('held', {
    price: '40', original: '80', discount: '50', days: '40', daysat: '40', score: '50', hot: '0',
    drop: '0', lowest: '1', hitlow: '0', fresh: '0', store: 'Zumiez'
}, 'Price unchanged since Sep 1', 'quiet-low', 'Verified low');
fillQuickView(heldCard);
const heldSignal = body.querySelector('.quick-signal');
assert.ok(heldSignal.matches('.is-held'));
assert.equal(heldSignal.querySelector('strong').textContent, 'Unchanged price, already low');
assert.match(heldSignal.textContent, /Verified low/);
assert.equal(body.querySelector('.is-drop'), null);
assert.equal(body.querySelector('.quick-chart'), null);
assert.equal(body.querySelector('.quick-stores'), null);
const heldMore = body.querySelector('.quick-more');
assert.equal(heldMore.querySelector('.quick-tracking').textContent, 'Tracking since Sep 1');
assert.equal(heldMore.querySelector('.quick-signal'), heldSignal);
assert.equal(body.querySelector('.quick-product').querySelector('.quick-signal'), null);
assert.equal(body.querySelectorAll('.quick-badge').length, 1);
assert.equal(body.querySelector('.quick-badge').textContent, 'All-time low');
assert.match(heldMore.querySelector('.quick-history').textContent, /90-day average/);
assert.equal(body.querySelector('.quick-gallery').tag, 'div');
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_card_tap_opens_the_quick_view_not_the_old_sheet(self):
        page = Path(__file__).with_name("page.py").read_text(encoding="utf-8")
        script = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        self.assertNotIn(">Close</button>", page)
        self.assertNotIn('id="productModal"', page)
        self.assertNotIn('id="modalClose"', page)
        self.assertNotIn('id="priceDrawer"', page)
        self.assertNotIn('id="drawerClose"', page)
        self.assertIn('class="quick-close filters-done" id="filtersClose" aria-label="Close filters">×</button>', page)
        deals = script[script.index("function wireDealEvents("):script.index("function backdropPixel(")]
        self.assertNotIn("openProduct(", deals)
        click = deals[deals.index('const row = event.target.closest(".deal-row, .deal-card");'):]
        self.assertIn("openQuickView(row, true)", click)
        self.assertIn("openQuickView(card, true, true)", deals)
        self.assertIn("function openProduct(", script)
        opener = script[script.index("function openProduct("):script.index("function closeProduct(")]
        self.assertIn("openQuickView(card, true, !!fromGroup)", opener)
        self.assertNotIn("productModal", opener)
        closer = script[script.index("function wireQuickView("):script.index("function placeScoreFloat(")]
        outside = closer[closer.index('document.addEventListener("click"'):]
        self.assertIn('closest(".deal-row, .deal-card")', outside)
        self.assertIn('!event.target.closest("a, button, input, select, label")', outside)

    def test_quick_view_opens_from_the_button_and_closes_cleanly(self):
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        self.assertNotIn("QUICK_OPEN_MS", source)
        self.assertNotIn("QUICK_CLOSE_MS", source)
        self.assertNotIn("onQuickEnter", source)
        self.assertNotIn("onQuickLeave", source)
        self.assertNotIn("setTimeout(() => openQuickView", source)
        self.assertIn('document.addEventListener("keydown", onDocumentEscape)', source)
        hover = source[source.index('addEventListener("mouseover"'):source.index('addEventListener("mouseout"')]
        self.assertNotIn("openQuickView", hover)
        logic = source[source.index("function quickGalleryImages("):source.index("function backdropPixel(")]
        script = r'''
const assert = require("node:assert/strict");
let quickCard = null;
let quickPinned = false;
let quickForceSheet = false;
let groupReturnFocus = null;
let sparkPinned = false;
function quickIsSheet() {
  if (window.innerWidth <= 800) return true;
  return window.matchMedia("(pointer: coarse)").matches;
}
function isQuickOpen() {
  const panelNode = document.getElementById("quickView");
  return !!(panelNode && !panelNode.hidden);
}
const queued = [];
const setTimeout = (fn) => { const id = queued.length + 1; queued.push({id, fn}); return id; };
const clearTimeout = (id) => { const index = queued.findIndex(item => item.id === id); if (index >= 0) queued.splice(index, 1); };
function flush() { const batch = queued.splice(0, queued.length); batch.forEach(item => item.fn()); }
function hideSparkTip() {}
function closeDrawer() {}
function closeSparkPanel() {}
function closeProduct() {}
function toggleStar() {}
function dealNode() { return null; }
function cardFor() { return null; }
function selectGroupOffer() {}
function moveGroupOffer() {}
function showSparkTip() {}
function nearestPoint() { return null; }
function placeScoreFloat() {}
function quickMoney(symbol, price) { return symbol + Number(price).toFixed(2); }
function quickPercent() { return "20% vs list"; }
function catalog() {
  return { generated: "2026-10-28", items: {
    a: {name: "Deck A", store: "Tactics", brand: "Misc", image: "https://example.com/a.jpg"},
    b: {name: "Deck B", store: "CCS", brand: "CCS", image: "https://example.com/b.jpg"}
  }};
}
function quickFacts() {
  return {specs: [{label: "Width", value: "9.75\""}, {label: "In stock", value: "8, 9"}], symbol: "$",
    viewUrl: "https://example.com/p", viewLabel: "View at Tactics", points: [], rows: [], stores: [], markers: []};
}
class Element {
  constructor(tag) {
    this.tag = tag; this.tagName = String(tag || "div").toUpperCase();
    this.children = []; this.style = {}; this.attrs = {}; this.className = "";
    this.events = {}; this.dataset = {}; this._text = ""; this.hidden = false;
    this.id = ""; this.parentElement = null;
  }
  append(...nodes) { nodes.forEach(node => { if (!node) return; node.parentElement = this; this.children.push(node); }); }
  appendChild(node) { this.append(node); }
  replaceChildren(...nodes) {
    this.children.forEach(node => { if (node) node.parentElement = null; });
    this.children = [];
    this.append(...nodes);
  }
  setAttribute(name, value) { this.attrs[name] = String(value); if (name === "id") this.id = String(value); if (name === "class") this.className = String(value); }
  getAttribute(name) { return this.attrs[name] || null; }
  addEventListener(name, callback) { this.events[name] = callback; }
  matches(selector) {
    if (!selector) return false;
    if (selector.includes(",")) return selector.split(",").some(part => this.matches(part.trim()));
    if (selector.startsWith("#")) return this.id === selector.slice(1);
    if (selector.startsWith(".")) {
      const name = selector.slice(1).split("[")[0];
      return name.split(".").filter(Boolean).every(part => this.className.split(/\s+/).includes(part));
    }
    return this.tag === selector.toLowerCase();
  }
  querySelectorAll(selector) {
    if (selector === "*") return this.children.flatMap(child => [child, ...child.querySelectorAll("*")]);
    if (selector.includes(",")) {
      const seen = new Set();
      const out = [];
      selector.split(",").forEach(part => this.querySelectorAll(part.trim()).forEach(node => {
        if (!seen.has(node)) { seen.add(node); out.push(node); }
      }));
      return out;
    }
    return this.children.flatMap(child => [child, ...child.querySelectorAll("*")]).filter(node => node.matches(selector));
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) {
    let node = this;
    while (node) {
      if (node.matches && node.matches(selector)) return node;
      node = node.parentElement || null;
    }
    return null;
  }
  contains(node) {
    if (!node) return false;
    if (node === this) return true;
    return this.children.some(child => child === node || (child.contains && child.contains(node)));
  }
  focus() {}
  get textContent() { return this.children.length ? this.children.map(child => child.textContent).join("") : this._text; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get classList() {
    const el = this;
    return {
      contains: name => el.className.split(/\s+/).includes(name),
      add: name => { if (!el.className.split(/\s+/).includes(name)) el.className = (el.className + " " + name).trim(); },
      remove: name => { el.className = el.className.split(/\s+/).filter(part => part && part !== name).join(" "); },
      toggle(name, force) {
        const on = el.className.split(/\s+/).includes(name);
        const next = force === undefined ? !on : !!force;
        if (next) { if (!on) el.className = (el.className + " " + name).trim(); }
        else el.className = el.className.split(/\s+/).filter(part => part && part !== name).join(" ");
        return next;
      }
    };
  }
  getBoundingClientRect() { return {left: 0, top: 0, right: 0, bottom: 0, width: 200, height: 240}; }
}
const listeners = [];
const panel = new Element("div");
panel.id = "quickView";
panel.hidden = true;
const dialog = new Element("div");
dialog.className = "quick-panel";
const body = new Element("div");
body.id = "quickBody";
dialog.append(body);
panel.append(dialog);
function makeCard(id) {
  const card = new Element("article");
  card.className = "deal-card";
  card.dataset = {id: id, price: "119.95", original: "149.94", discount: "20", store: "Tactics", lowest: "1"};
  card.getBoundingClientRect = () => ({left: 120, right: 300, top: 180, bottom: 460, width: 180, height: 280});
  const button = new Element("button");
  button.className = "card-quick";
  card.append(button);
  return {card, button};
}
const cardA = makeCard("a");
const cardB = makeCard("b");
const docBody = new Element("body");
const document = {
  addEventListener(type, fn, capture) { listeners.push({type, fn, capture: !!capture}); },
  getElementById(id) {
    if (id === "quickView") return panel;
    if (id === "quickBody") return body;
    return null;
  },
  createElement(tag) { return new Element(tag); },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  activeElement: null,
  body: docBody
};
const window = {
  innerWidth: 1200,
  innerHeight: 900,
  matchMedia() { return {matches: false}; },
  addEventListener() {}
};
function dispatch(type, target, extra) {
  const event = {type, target, key: extra && extra.key, relatedTarget: extra && extra.relatedTarget, clientX: 0, clientY: 0,
    preventDefault() {}, stopPropagation() { event.stopped = true; }};
  listeners.filter(item => item.type === type && item.capture).forEach(item => { if (!event.stopped) item.fn(event); });
  if (!event.stopped && target && target.events && target.events[type]) target.events[type](event);
  listeners.filter(item => item.type === type && !item.capture).forEach(item => { if (!event.stopped) item.fn(event); });
  return event;
}
'''
        script += logic + r'''
wireDealEvents();
dispatch("mouseover", cardA.card);
dispatch("mouseout", cardA.card);
flush();
assert.equal(isQuickOpen(), false, "hover does not open");
assert.equal(queued.length, 0, "hover does not arm a timer");
dispatch("click", cardA.card);
flush();
assert.equal(isQuickOpen(), false, "clicking the card does not open");
dispatch("keydown", cardA.button, {key: "Enter"});
assert.equal(isQuickOpen(), true, "Enter on Quick view opens");
assert.equal(quickCard.dataset.id, "a");
assert.equal(body.querySelector(".quick-title").textContent, "Deck A");
dispatch("keydown", cardB.button, {key: " "});
assert.equal(isQuickOpen(), true);
assert.equal(quickCard.dataset.id, "b");
assert.equal(body.querySelector(".quick-title").textContent, "Deck B");
for (let round = 0; round < 4; round++) {
  dispatch("click", cardA.button);
  flush();
  assert.equal(isQuickOpen(), true, "card A stays open, round " + round);
  assert.equal(quickCard.dataset.id, "a");
  assert.equal(body.querySelector(".quick-title").textContent, "Deck A");
  dispatch("click", cardB.button);
  flush();
  assert.equal(isQuickOpen(), true, "card B stays open, round " + round);
  assert.equal(quickCard.dataset.id, "b");
  assert.equal(body.querySelector(".quick-title").textContent, "Deck B");
}
onDocumentEscape({key: "Escape", preventDefault() {}});
assert.equal(isQuickOpen(), false, "Escape closes");
assert.equal(quickCard, null);
dispatch("click", cardA.button);
assert.equal(isQuickOpen(), true);
body.querySelector(".quick-close").events.click({preventDefault() {}, stopPropagation() {}});
assert.equal(isQuickOpen(), false, "X closes");
dispatch("click", cardA.card);
assert.equal(isQuickOpen(), false);
window.innerWidth = 390;
dispatch("click", cardB.card);
assert.equal(isQuickOpen(), true, "a phone tap still opens");
assert.equal(quickCard.dataset.id, "b");
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
