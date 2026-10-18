"""Quick-view rendering and placement regressions; uses the existing Node test runtime."""

import subprocess
import unittest
from pathlib import Path


class QuickViewTests(unittest.TestCase):
    def test_lazy_content_and_viewport_placement(self):
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        rendering = source[source.index("function fillQuickView("):source.index("function appendQuickScore(")]
        placement = source[source.index("function quickTopLimit("):source.index("function closeQuickView(")]
        script = r'''
const assert = require('node:assert/strict');
class Element {
    constructor(tag = 'div') { this.tag = tag; this.children = []; this.style = {}; this.attrs = {}; this.className = ''; }
    append(...nodes) { this.children.push(...nodes); }
    appendChild(node) { this.append(node); }
    replaceChildren(...nodes) { this.children = nodes; }
    setAttribute(name, value) { this.attrs[name] = value; }
    addEventListener() {}
    cloneNode() { const e = new Element(this.tag); e.className = this.className; e.children = this.children.map(c => c.cloneNode()); return e; }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    querySelectorAll(selector) {
        const matches = n => selector.startsWith('.') ? n.className.split(' ').includes(selector.slice(1)) : n.tag === selector;
        return this.children.flatMap(n => [...(matches(n) ? [n] : []), ...n.querySelectorAll(selector)]);
    }
    get classList() {
        return {contains: c => this.className.split(' ').includes(c), add: c => { this.className += ' ' + c; }};
    }
    getBoundingClientRect() { return {height: this.naturalHeight || 500, width: parseFloat(this.style.width) || 560}; }
}
const body = new Element();
const dialog = new Element(); dialog.className = 'quick-panel';
const panel = new Element(); panel.append(dialog);
const sticky = {getBoundingClientRect: () => ({bottom: 100})};
const document = {
    getElementById: id => ({quickView: panel, quickBody: body, stickyBar: sticky}[id]),
    createElement: tag => new Element(tag), body: new Element()
};
const window = {innerWidth: 1200, innerHeight: 900};
const item = {name: 'Nike SB Dunk Low Pro', store: 'CCS', first: '2026-10-17'};
const catalog = () => ({items: {shoe: item}, generated: '2026-10-18'});
const facts = {points: [[1, 70], [2, 70]], rows: [{label: 'List price', value: '$100'}],
    specs: [{label: 'In stock', value: '6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10, 10.5, 11'}], stores: [], symbol: '$'};
const quickFacts = () => facts;
const quickMoney = (symbol, price) => symbol + Number(price).toFixed(2);
const quickPercent = () => '30% off';
const quickShortDate = () => 'Oct 17';
const syncQuickStar = () => {};
const appendQuickScore = () => {};
let chartCalls = 0;
const drawQuickChart = () => { chartCalls++; };
const image = new Element('span'); image.className = 'hero-wrap'; image.append(new Element('img'));
let anchor = {left: 1000, right: 1190, top: 780, bottom: 880, width: 190, height: 100};
const card = {dataset: {id: 'shoe', price: '70', discount: '30'}, querySelector: () => image, getBoundingClientRect: () => anchor};
const closeQuickView = () => { throw new Error('Unexpected close'); };
'''
        script += rendering + placement + r'''
fillQuickView(card);
assert.equal(chartCalls, 0, 'short history must not draw a chart');
assert.equal(body.querySelector('.quick-tracking').textContent, 'Tracking since Oct 17');
assert.equal(body.querySelector('.quick-title').textContent, item.name);
assert.equal(body.querySelector('.quick-kicker').textContent, 'CCS');
assert.equal(body.querySelector('.quick-price').children[0].textContent, '$70.00');
assert.equal(body.querySelector('.quick-close').attrs['aria-label'], 'Close quick view');
assert.equal(body.querySelectorAll('.quick-spec-chip').length, 10);
assert.equal(body.querySelectorAll('.quick-spec-chip').at(-1).textContent, '11');
assert.notEqual(body.querySelector('.quick-image-frame'), image, 'clone existing image and fallback');
facts.points = [[1,70],[2,69],[3,68],[4,67]];
fillQuickView(card); assert.equal(chartCalls, 0, 'four points still use note');
facts.points.push([5,66]);
fillQuickView(card); assert.equal(chartCalls, 1, 'five points draw the chart');
assert.equal(body.querySelector('.quick-tracking'), null, 'no stale note on next open');
placeQuickView(card);
assert.equal(panel.style.width, '560px');
assert.equal(panel.style.height, 'auto', 'never constrain desktop content to card height');
assert.equal(panel.style.left, '630px', 'flip left at right edge');
assert.equal(panel.style.top, '392px', 'flip upward at bottom edge');
anchor = {...anchor, left: -30, right: 160, top: 0};
placeQuickView(card);
assert.equal(panel.style.left, '8px');
assert.equal(panel.style.top, '104px', 'keep clear of sticky navigation');
panel.naturalHeight = 850;
placeQuickView(card);
assert.ok(panel.classList.contains('is-sheet'), 'short viewport uses sheet, never clips content');
assert.equal(dialog.attrs['aria-modal'], 'true');
assert.equal(panel.style.width, '');
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
