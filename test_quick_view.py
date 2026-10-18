"""Quick-view gallery rendering and placement regressions using Node."""

import subprocess
import unittest
from pathlib import Path


class QuickViewTests(unittest.TestCase):
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
assert.equal(body.querySelector('.quick-kicker').textContent, 'CCS');
assert.equal(body.querySelector('.quick-price').children[0].textContent, '$70.00');
assert.equal(body.querySelector('.quick-close').attrs['aria-label'], 'Close quick view');
assert.equal(body.querySelectorAll('.quick-spec-chip').length, 10);
assert.equal(body.querySelectorAll('.quick-spec-chip').at(-1).textContent, '11');
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
assert.equal(panel.style.width, '720px');
assert.equal(panel.style.height, 'auto');
assert.equal(panel.style.left, '470px', 'flip left at right edge');
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


if __name__ == "__main__":
    unittest.main()
