"""Card view: the product photo is the hero, and secondary copy stays available."""

import subprocess
import unittest
from pathlib import Path

from report import build_report_html


def _deck(price, url, store, name, image="https://example.com/deck.jpg"):
    return {
        "name": name,
        "url": url,
        "price_new": price,
        "price_old": "80.00",
        "part": "Decks",
        "store": store,
        "image": image,
    }


class CardHeroTests(unittest.TestCase):
    def test_photo_slot_is_about_half_the_card_and_secondary_copy_is_quiet(self):
        css = Path("page.css").read_text(encoding="utf-8")
        mobile = Path("mobile.css").read_text(encoding="utf-8")
        js = Path("page.js").read_text(encoding="utf-8")
        media = css.split(".deal-card .media {", 1)[1].split("}", 1)[0]
        self.assertIn("aspect-ratio: 100 / 64", media)
        self.assertIn("min-height: 140px", media)
        self.assertIn("max-height: 210px", media)
        self.assertIn(".deal-card .card-face,\n.deal-card .price-since", css)
        self.assertIn(".deal-card .avg-price", css)
        self.assertIn('content: "No photo"', css)
        self.assertIn(".deal-card .hero-wrap.is-missing", css)
        phone = mobile.split(".deal-card .media {", 1)[1].split("}", 1)[0]
        self.assertIn("aspect-ratio: 1 / 1", phone)
        last = css.rfind(".deal-card .media .hero-wrap")
        self.assertGreater(last, css.find("height: 72px"))
        self.assertNotIn("height: 72px", css[last:last + 500])
        self.assertIn("fitCardPhotos();", js)
        self.assertIn("function heroFitSize(", js)
        self.assertIn("quick-stage", js)
        self.assertIn(".quick-stage", css)

        deck = _deck("39.99", "https://example.com/deck", "Zumiez", "Baker Brand Logo 8.25 Skateboard Deck")
        bare = _deck(
            "39.99",
            "https://example.com/missing-photo",
            "CCS",
            "Blank Photo 8.25 Skateboard Deck",
            image="",
        )
        html = build_report_html(
            {"Zumiez_Decks": [deck], "CCS_Decks": [bare]},
            {},
            generated_at="2026-10-18T19:12:00+00:00",
        )
        card = html.split("https://example.com/deck", 1)[1].split("</article>", 1)[0]
        self.assertIn("Now:", card)
        self.assertIn('class="card-face"', card)
        self.assertIn('class="price-since"', card)
        self.assertIn('class="card-sparkline"', card)
        self.assertIn("card-off", card)
        self.assertIn(">Details</button>", card)
        missing = next(
            part.split("</article>", 1)[0]
            for part in html.split('<article class="deal-card')[1:]
            if "missing-photo" in part
        )
        self.assertIn('class="hero ph"', missing)
        self.assertNotIn("<img", missing)
        # Three-line titles stay, so the price row does not jump between cards.
        self.assertIn("flex: 0 0 calc(1.25em * 3)", html)
        self.assertIn("line-clamp: 3", html)

    def test_content_box_trims_padding_and_keeps_both_orientations(self):
        source = Path("page.js").read_text(encoding="utf-8")
        start = source.index("function backdropPixel(")
        end = source.index("function measureContent(")
        script = source[start:end] + r"""
const assert = require("node:assert/strict");
assert.equal(backdropPixel(250, 250, 250, 255), true);
assert.equal(backdropPixel(245, 245, 245, 255), true);
assert.equal(backdropPixel(200, 200, 200, 255), false);
assert.equal(backdropPixel(10, 10, 10, 0), true);

const pixels = new Uint8ClampedArray(10 * 10 * 4);
pixels.fill(255);
for (let y = 1; y <= 8; y++) {
  for (let x = 4; x <= 5; x++) {
    const i = (y * 10 + x) * 4;
    pixels[i] = pixels[i + 1] = pixels[i + 2] = 20;
    pixels[i + 3] = 255;
  }
}
const deck = contentBox(pixels, 10, 10, 100, 100);
assert.ok(Math.abs(deck.x - 40) < 0.01, deck.x);
assert.ok(Math.abs(deck.y - 10) < 0.01, deck.y);
assert.ok(Math.abs(deck.w - 20) < 0.01, deck.w);
assert.ok(Math.abs(deck.h - 80) < 0.01, deck.h);
assert.ok(deck.h > deck.w, "vertical deck stays tall");

pixels.fill(255);
for (let y = 4; y <= 5; y++) {
  for (let x = 1; x <= 8; x++) {
    const i = (y * 10 + x) * 4;
    pixels[i] = 20; pixels[i + 1] = 30; pixels[i + 2] = 40; pixels[i + 3] = 255;
  }
}
const shoe = contentBox(pixels, 10, 10, 100, 100);
assert.ok(shoe.w > shoe.h, "horizontal product stays wide");

pixels.fill(30);
const full = contentBox(pixels, 10, 10, 80, 80);
assert.equal(full.x, 0);
assert.equal(full.y, 0);
assert.equal(full.w, 80);
assert.equal(full.h, 80);

const pad = paddedBox(deck, 100, 100);
assert.ok(pad.w > deck.w && pad.w <= 100);
assert.ok(pad.h > deck.h && pad.h <= 100);
assert.ok(pad.x < deck.x && pad.y < deck.y);
assert.equal(pad.iw, 100);
assert.equal(pad.ih, 100);

const slotW = 280;
const slotH = 180;
const tall = heroFitSize(deck.w / deck.h, slotW, slotH);
assert.ok(Math.abs(tall.height - slotH) < 0.01, "a deck fills the slot height");
assert.ok(tall.width < slotW * 0.5, "a deck does not get stretched wide");
const wide = heroFitSize(shoe.w / shoe.h, slotW, slotH);
assert.ok(Math.abs(wide.width - slotW) < 0.01, "a shoe fills the slot width");
assert.ok(wide.height < slotH, "a shoe is not cropped to the slot height");
assert.equal(heroFitSize(1, 0, 0), null);
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
