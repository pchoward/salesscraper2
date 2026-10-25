"""Group Across Stores comparison: price-only cheapest, stock, and empty states.

The live catalog can have no cross-store matches. These cases use fixture offers
and a report built from the existing matcher, without changing that matcher.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

from report import build_report_html


def _deck(price, url, store, name):
    return {
        "name": name,
        "url": url,
        "price_new": price,
        "price_old": "90.00",
        "part": "Decks",
        "store": store,
        "image": "https://example.com/deck.jpg",
    }


def _history(url, price, stock=""):
    entry = {
        "name": "tracked",
        "store": "Zumiez",
        "part": "Decks",
        "first_seen": "2026-07-20",
        "last_seen": "2026-10-18",
        "observation_count": 3,
        "all_time_low": price,
        "all_time_low_date": "2026-10-18",
        "prices": {"2026-07-20": price, "2026-09-01": price, "2026-10-18": price},
    }
    if stock:
        entry["stock"] = stock
    return {url: entry}


def _rank_source():
    source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
    start = source.index("const GROUP_PRICE_NOTE")
    end = source.index("function rowGroupOffer(")
    return source[start:end]


class GroupCompareTests(unittest.TestCase):
    def test_price_only_ranking_for_many_one_and_zero_offers(self):
        # Fixture, not the live catalog: a sold-out listing is cheaper than the
        # two offers that are actually on sale. `cheapest: true` is the raw
        # price flag and must not win while that offer is sold out.
        fixture = [
            {
                "id": "ccs",
                "store": "CCS",
                "price": 49.0,
                "url": "https://example.com/ccs",
                "name": "Baker Figgy Divine Evil Deck 8.125",
                "availability": "Sold out",
                "currency": "USD",
                "cheapest": True,
            },
            {
                "id": "sw",
                "store": "SkateWarehouse",
                "price": 59.98,
                "url": "https://example.com/sw",
                "name": "Baker Figgy Divine Evil Deck 8.12",
                "availability": "On sale",
                "currency": "USD",
                "cheapest": False,
            },
            {
                "id": "zumiez",
                "store": "Zumiez",
                "price": 64.99,
                "url": "https://example.com/z",
                "name": "Baker Figgy Divine Evil Deck 8.125",
                "availability": "On sale",
                "currency": "USD",
                "cheapest": False,
            },
        ]
        script = _rank_source() + "\nconst fixture = " + json.dumps(fixture) + r"""
const assert = require("node:assert/strict");
const ranked = rankGroupOffers(fixture);
assert.equal(ranked.mode, "compare");
assert.equal(ranked.featured.store, "SkateWarehouse");
assert.equal(ranked.featured.available, true);
assert.equal(groupKicker(ranked), "Cheapest available · price only");
assert.equal(groupNote(ranked).includes("Delivery charges and tax are not included."), true);
assert.equal(groupNote(ranked).includes("A lower listed price is sold out."), true);
assert.equal(ranked.offers.map(offer => offer.store).join(","), "SkateWarehouse,Zumiez,CCS");
assert.equal(groupGapText(ranked.offers[1], ranked.featured), "+$5.01");
assert.equal(groupGapText(ranked.offers[2], ranked.featured), "−$10.98");
assert.equal(ranked.offers[2].available, false);
for (const row of [ranked, ...ranked.offers]) {
    assert.equal(Object.prototype.hasOwnProperty.call(row, "shipping"), false);
    assert.equal(Object.prototype.hasOwnProperty.call(row, "tax"), false);
}
const tied = rankGroupOffers([
    {id: "a", store: "Tactics", price: 40, availability: "On sale", currency: "USD"},
    {id: "b", store: "CCS", price: 40, availability: "On sale", currency: "USD"}
]);
assert.equal(tied.featured.store, "CCS");
assert.equal(groupGapText(tied.offers.find(offer => offer.store === "Tactics"), tied.featured), "Same price");
const single = rankGroupOffers([{id: "only", store: "Zumiez", price: 42, availability: "On sale"}]);
assert.equal(single.mode, "single");
assert.equal(groupKicker(single), "One store in this view");
assert.equal(groupKicker(single).includes("Cheapest"), false);
assert.equal(groupNote(single).includes("Only one matching store"), true);
assert.equal(groupNote(single).includes("Delivery charges and tax are not included."), true);
assert.equal(rankGroupOffers([]).mode, "empty");
assert.equal(rankGroupOffers([{id: "x", price: "nope"}]).mode, "empty");
assert.equal(groupNote(rankGroupOffers([])), "");
const gone = rankGroupOffers([
    {id: "g", store: "CCS", price: 10, availability: "Gone"},
    {id: "n", store: "Tactics", price: 12, availability: "No longer listed"},
    {id: "z", store: "Zumiez", price: 30, availability: "On sale"}
]);
assert.equal(gone.featured.store, "Zumiez");
assert.equal(gone.featured.available, true);
const none = rankGroupOffers([
    {id: "g", store: "CCS", price: 10, availability: "Sold out"},
    {id: "z", store: "Zumiez", price: 12, availability: "Gone"}
]);
assert.equal(none.anyAvailable, false);
assert.equal(none.featured.store, "CCS");
assert.equal(groupKicker(none), "Lowest listed price · price only");
assert.equal(groupKicker(none).includes("available"), false);
const euros = rankGroupOffers([
    {id: "a", store: "CCS", price: 40, availability: "On sale", currency: "EUR"},
    {id: "b", store: "Tactics", price: 45.5, availability: "On sale", currency: "EUR"}
]);
assert.equal(groupMoney("EUR", euros.featured.price), "€40.00");
assert.equal(groupGapText(euros.offers[1], euros.featured), "+€5.50");
const mixed = rankGroupOffers([
    {id: "a", store: "CCS", price: 40, availability: "On sale", currency: "USD"},
    {id: "b", store: "Tactics", price: 30, availability: "On sale", currency: "EUR"}
]);
assert.equal(groupGapText(mixed.offers.find(offer => !offer.featured), mixed.featured), "");
assert.equal(groupOfferStep(0, 3, "ArrowDown"), 1);
assert.equal(groupOfferStep(0, 3, "ArrowRight"), 1);
assert.equal(groupOfferStep(0, 3, "ArrowUp"), 2);
assert.equal(groupOfferStep(2, 3, "ArrowDown"), 0);
assert.equal(groupOfferStep(1, 3, "Home"), 0);
assert.equal(groupOfferStep(0, 3, "End"), 2);
assert.equal(offerAvailable(""), true);
assert.equal(offerAvailable("On sale"), true);
assert.equal(offerAvailable("Sold out"), false);
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_report_match_is_ranked_from_existing_offers(self):
        zumiez = _deck("64.99", "https://example.com/z", "Zumiez", "Baker Figgy Divine Evil Deck 8.125")
        warehouse = _deck("59.98", "https://example.com/sw", "SkateWarehouse", "Baker Figgy Divine Evil Deck 8.12 x 31.875")
        sold = _deck("49.00", "https://example.com/ccs", "CCS", "Baker Figgy Divine Evil Deck 8.125")
        alone = _deck("40.00", "https://example.com/girl", "Tactics", "Girl Howard Fullcourt Twin 8.25 Deck")
        history = {}
        history.update(_history(zumiez["url"], 64.99))
        history.update(_history(warehouse["url"], 59.98))
        history.update(_history(sold["url"], 49.00, stock="out_of_stock"))
        html = build_report_html(
            {"Zumiez_Decks": [zumiez], "SkateWarehouse_Decks": [warehouse], "CCS_Decks": [sold], "Tactics_Decks": [alone]},
            {},
            price_history=history,
            generated_at="2026-10-18T12:00:00+00:00",
        )
        keys = re.findall(r'data-group="([^"]*)"', html)
        filled = [key for key in keys if key]
        self.assertEqual(len(set(filled)), 1)
        self.assertGreaterEqual(filled.count(filled[0]), 3)
        self.assertIn('id="groupBoard"', html)
        self.assertIn('id="groupToggle"', html)
        catalog = json.loads(html.split('id="catalogJson">', 1)[1].split("</script>", 1)[0])
        by_url = {}
        for item in catalog["items"].values():
            for offer in item.get("offers") or []:
                by_url[offer["url"]] = offer
        self.assertEqual(by_url[sold["url"]]["availability"], "Sold out")
        self.assertEqual(by_url[sold["url"]]["cheapest"], True)
        self.assertEqual(by_url[warehouse["url"]]["availability"], "On sale")
        offers = []
        for url, item_id in (
            (sold["url"], "ccs"),
            (warehouse["url"], "sw"),
            (zumiez["url"], "z"),
        ):
            offer = dict(by_url[url])
            offer["id"] = item_id
            offers.append(offer)
        script = _rank_source() + "\nconst offers = " + json.dumps(offers) + r"""
const assert = require("node:assert/strict");
const ranked = rankGroupOffers(offers);
if (ranked.featured.store !== "SkateWarehouse") throw new Error(ranked.featured.store);
if (!ranked.featured.available) throw new Error("featured sold out");
if (ranked.offers.some(offer => offer.store === "CCS" && offer.featured)) throw new Error("sold out featured");
if (!groupNote(ranked).includes("Delivery charges and tax are not included.")) throw new Error(groupNote(ranked));
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        painter = source[source.index("function applyGroupVisibility("):source.index("function mirrorCardFlags(")]
        self.assertIn("paintGroupBoard(visible)", painter)
        self.assertIn("row.dataset.group", painter)
        self.assertNotIn("product_identity", source)
        self.assertNotIn("cross_store_groups", source)
        label = source[source.index("const GROUP_CHEAPEST_LABEL"):source.index("function groupNote(")]
        self.assertIn("function rankGroupOffers(", label)
        self.assertIn("Cheapest available · price only", label)
        self.assertNotIn("offer.cheapest", label)

    def test_comparison_styles_exist_for_desktop_and_phone(self):
        page = Path(__file__).with_name("page.css").read_text(encoding="utf-8")
        flat = page.index(".compare-card, .group-card, .offer")
        self.assertGreater(page.index(".group-board .group-card"), flat)
        self.assertIn(".group-offer.is-featured", page)
        self.assertIn(".group-kicker", page)
        self.assertIn(".stock.is-out", page)
        phone = Path(__file__).with_name("mobile.css").read_text(encoding="utf-8")
        block = phone.split("@media (max-width: 800px)", 1)[1]
        rules = block.split(".group-offer", 1)[1]
        self.assertIn("min-height: 2.75rem", rules)
        self.assertIn(".group-offer.is-featured .amt", block)
