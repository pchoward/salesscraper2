"""Deck length buckets, sidebar order, card grid, and cheap page-load wins."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from page import (
    CARD_PAGE_SIZE,
    LENGTH_BOUNDARY_TIP,
    build_length_buckets,
    length_bucket_for,
    parse_length,
)
from report import build_report_html


ROOT = Path(__file__).resolve().parent


def _item(name, part, url, **extra):
    row = {
        "name": name,
        "url": url,
        "price_new": "40.00",
        "price_old": "80.00",
        "part": part,
        "store": "Zumiez",
    }
    row.update(extra)
    return row


def _catalog():
    decks = []
    lengths = [28.5, 29.1, 30.0, 31.0, "31.75\"", 32.5, 33.0, 33.3]
    for index, length in enumerate(lengths):
        decks.append(_item(
            f"Powell Peralta Ripper 8.25 x {length} Skateboard Deck wheelbase 14.{index}",
            "Decks",
            f"https://example.com/deck-{index}",
            image="https://example.com/deck.jpg",
        ))
    for index in range(CARD_PAGE_SIZE):
        decks.append(_item(
            f"Powell Peralta Ripper 8.25 x 32.{index % 10} Skateboard Deck",
            "Decks",
            f"https://example.com/extra-deck-{index}",
        ))
    trucks = [
        _item(
            "Independent 149 Hollow Low Stage 11 Skateboard Truck",
            "Trucks",
            f"https://example.com/truck-{index}",
        )
        for index in range(5)
    ]
    wheels = [
        _item(
            "Spitfire Formula Four Conical Full 54mm 99a Skateboard Wheels",
            "Wheels",
            f"https://example.com/wheel-{index}",
        )
        for index in range(5)
    ]
    bearings = [
        _item("Bones Reds ABEC 7 Bearings", "Bearings", f"https://example.com/bearing-{index}")
        for index in range(5)
    ]
    sneakers = [
        _item(
            "Nike SB Dunk Low",
            "Sneakers",
            f"https://example.com/shoe-{index}",
            shoe_sizes=["9", "10"],
        )
        for index in range(5)
    ]
    protection = [
        _item(
            "Pro-Tec Classic Helmet",
            "Protection",
            f"https://example.com/helmet-{index}",
            protection_sizes=["M", "L"],
        )
        for index in range(5)
    ]
    return {
        "Zumiez_Decks": decks,
        "Zumiez_Trucks": trucks,
        "Zumiez_Wheels": wheels,
        "Zumiez_Bearings": bearings,
        "Zumiez_Sneakers": sneakers,
        "Zumiez_Protection": protection,
    }


def _sections(html):
    rail = html.split('<div class="rail">', 1)[1].split('<div class="board">', 1)[0]
    found = []
    for chunk in rail.split("<section"):
        if "data-section=" not in chunk:
            continue
        attrs = chunk.split(">", 1)[0]
        section = attrs.split('data-section="', 1)[1].split('"', 1)[0]
        owner = ""
        if 'data-for="' in attrs:
            owner = attrs.split('data-for="', 1)[1].split('"', 1)[0]
        hidden = " hidden" in attrs or attrs.endswith(" hidden")
        found.append({"id": section, "for": owner, "hidden": hidden})
    return found


def _visible(sections, part):
    return [
        item["id"]
        for item in sections
        if not item["hidden"] and (not item["for"] or item["for"] == part)
    ]


class LengthBucketTests(unittest.TestCase):
    def test_boundaries_include_the_lower_end_and_parse_inch_marks(self):
        self.assertEqual(parse_length("31.75\""), 31.75)
        self.assertEqual(parse_length("30.0"), 30.0)
        self.assertEqual(parse_length(30), 30.0)
        buckets = build_length_buckets([28.5, 29.1, 30.0, 31.0, "31.75\"", 32.5, 33.0, 33.3])
        ids = [bucket["id"] for bucket in buckets]
        self.assertEqual(ids, ["28-29", "29-30", "30-31", "31-32", "32-33", "33+"])
        self.assertIn("30\u201331", buckets[2]["label"])
        self.assertIn('33"+', buckets[-1]["label"])
        # 30.0 is the start of 30–31, not the end of 29–30.
        self.assertEqual(length_bucket_for(30.0, buckets), "30-31")
        self.assertEqual(length_bucket_for("30.0", buckets), "30-31")
        self.assertEqual(length_bucket_for("30.0\"", buckets), "30-31")
        self.assertEqual(length_bucket_for(29.999, buckets), "29-30")
        self.assertEqual(length_bucket_for("31.75\"", buckets), "31-32")
        self.assertEqual(length_bucket_for(31.75, buckets), "31-32")
        self.assertEqual(length_bucket_for(32.999, buckets), "32-33")
        self.assertEqual(length_bucket_for(33.0, buckets), "33+")
        self.assertEqual(length_bucket_for("33.0\"", buckets), "33+")
        self.assertEqual(length_bucket_for(28.5, buckets), "28-29")
        # An open bottom still includes only lengths below its upper end.
        under = [{"id": "under-29", "min": None, "max": 29}, {"id": "29-30", "min": 29, "max": 30}]
        self.assertEqual(length_bucket_for(28.9, under), "under-29")
        self.assertEqual(length_bucket_for(29.0, under), "29-30")
        self.assertIn("lower end", LENGTH_BOUNDARY_TIP)
        self.assertIn('30.0"', LENGTH_BOUNDARY_TIP)

    def test_catalog_ends_follow_the_lengths_that_exist(self):
        short = build_length_buckets([31.2, 31.75, 31.9])
        self.assertEqual([bucket["id"] for bucket in short], ["31-32"])
        self.assertIsNotNone(short[0]["max"])
        topped = build_length_buckets([32.1, 33.0])
        self.assertEqual([bucket["id"] for bucket in topped], ["32-33", "33+"])
        self.assertIsNone(topped[-1]["max"])

    def test_page_chips_are_buckets_with_the_boundary_tooltip(self):
        html = build_report_html(_catalog(), {}, generated_at="2026-10-11T21:46:35+00:00")
        self.assertIn('data-section="length" data-for="Decks"', html)
        self.assertIn(">Deck Length<", html)
        self.assertIn('data-value="30-31"', html)
        self.assertIn('data-value="33+"', html)
        self.assertIn("30.0&quot; is in 30", html)
        self.assertNotIn('data-value="31.75"', html)
        chip = html.split('data-value="30-31"', 1)[1].split("</button>", 1)[0]
        self.assertIn("lower end", chip)
        self.assertIn(">30", chip)


class FilterOrderTests(unittest.TestCase):
    def test_brand_then_main_size_then_secondary_specs_then_the_rest(self):
        html = build_report_html(_catalog(), {}, generated_at="2026-10-11T21:46:35+00:00")
        sections = _sections(html)
        canon = [
            "brand",
            "width", "trucksize", "diameter", "shoesize", "protsize", "abec",
            "length", "wheelbase", "truckheight", "construction", "duro", "shape", "prottype",
            "price", "discount", "score", "deals", "interval",
        ]
        present = [item["id"] for item in sections if item["id"] in canon]
        self.assertEqual(present, [item for item in canon if item in present])
        expected = {
            "Decks": ["brand", "width", "length", "wheelbase", "price"],
            "Trucks": ["brand", "trucksize", "truckheight", "construction", "price"],
            "Wheels": ["brand", "diameter", "duro", "shape", "price"],
            "Sneakers": ["brand", "shoesize", "price"],
            "Protection": ["brand", "protsize", "prottype", "price"],
            "Bearings": ["brand", "abec", "price"],
            "Accessories": ["brand", "price"],
            "Completes": ["brand", "price"],
        }
        for part, chain in expected.items():
            order = _visible(sections, part)
            indexes = [order.index(item) for item in chain]
            self.assertEqual(indexes, sorted(indexes), f"{part}: {order}")
            self.assertEqual(order[0], "brand", part)
            self.assertLess(order.index(chain[-2] if part not in {"Accessories", "Completes"} else "brand"), order.index("price"), part)


class GridAndLoadTests(unittest.TestCase):
    def test_desktop_grid_caps_at_eight_columns(self):
        css = (ROOT / "page.css").read_text(encoding="utf-8")
        mobile = (ROOT / "mobile.css").read_text(encoding="utf-8")
        last = css.split(".card-grid {")[-1].split("}", 1)[0]
        self.assertIn("calc((100% - 7 * 8px) / 8)", last)
        self.assertIn("170px", last)
        self.assertNotIn("minmax(170px, 1fr)", css)
        phone = mobile.split(".card-grid {", 1)[1].split("}", 1)[0]
        self.assertIn("minmax(160px, 1fr)", phone)
        self.assertNotIn("7 * 8px", phone)

    def test_first_page_of_cards_is_mounted_and_images_wait(self):
        html = build_report_html(_catalog(), {}, generated_at="2026-10-11T21:46:35+00:00")
        grid = html.split('id="cardGrid">', 1)[1].split('id="showMoreCards"', 1)[0]
        pool = html.split('id="cardPool"', 1)[1].split('id="groupBoard"', 1)[0]
        self.assertEqual(grid.count("<article"), CARD_PAGE_SIZE)
        self.assertGreater(pool.count("<article"), 0)
        self.assertIn(">Show more<", html)
        self.assertIn("function syncMountedCards(", html)
        photo = grid.split("<img ", 1)[1].split(">", 1)[0]
        self.assertIn('decoding="async"', photo)
        self.assertIn('loading="lazy"', photo)
        self.assertIn('width="200"', photo)
        self.assertIn('height="200"', photo)
        spark = grid.split('class="spark-hit', 1)[1].split("</button>", 1)[0]
        self.assertNotIn("<svg", spark)
        self.assertIn("function refreshCharts(", html)

    def test_sidebar_headers_match_the_keepa_panel(self):
        css = (ROOT / "page.css").read_text(encoding="utf-8")
        panel = css.split("Keepa-style filter panel", 1)[1]
        self.assertIn("border: 1px solid var(--grey-200)", panel)
        self.assertIn("background: var(--grey-50)", panel)
        self.assertIn("border-top: 1px solid var(--grey-200)", panel)
        self.assertIn("border-bottom: 1px solid var(--grey-200)", panel)
        self.assertIn("justify-content: flex-start", panel)
        self.assertIn('.sidebar .filter-section > .section-toggle::before', panel)
        self.assertIn('content: "▸"', panel)
        self.assertIn('content: "▾"', panel)
        self.assertIn("background: var(--grey-0)", panel.split(".section-body", 1)[1])

    def test_length_filter_matches_buckets_in_the_browser_script(self):
        buckets = build_length_buckets([28.5, 29.0, 30.0, "31.75\"", 32.4, 33.0])
        source = (ROOT / "page.js").read_text(encoding="utf-8")
        script = """
const assert = require("node:assert/strict");
const document = { addEventListener() {} };
const window = {};
global.document = document;
global.window = window;
const LENGTH_BUCKETS = __BUCKETS__;
__SOURCE__
assert.equal(parseLength("31.75\\""), 31.75);
assert.equal(parseLength("30.0"), 30);
assert.equal(lengthBucketFor(30), "30-31");
assert.equal(lengthBucketFor("30.0\\""), "30-31");
assert.equal(lengthBucketFor(29.999), "29-30");
assert.equal(lengthBucketFor("31.75\\""), "31-32");
assert.equal(lengthBucketFor(33), "33+");
assert.equal(lengthBucketFor(32.999), "32-33");
assert.equal(normalizeLengthParam("30.0,31.75\\""), "30-31,31-32");
assert.equal(normalizeLengthParam("33+"), "33+");
state.length = "30-31,31-32";
assert.deepEqual(selectedLengths(), ["30-31", "31-32"]);
assert.equal(lengthAllowed("30.0", selectedLengths()), true);
assert.equal(lengthAllowed("31.75\\"", selectedLengths()), true);
assert.equal(lengthAllowed("29.5", selectedLengths()), false);
assert.equal(lengthAllowed("33.0", selectedLengths()), false);
state.length = "29-30,33+";
assert.equal(lengthAllowed("30", selectedLengths()), false);
assert.equal(lengthAllowed("33", selectedLengths()), true);
state.part = "Decks";
state.length = "30-31";
const row = { dataset: {
    part: "Decks", length: "30", size: "8.25", search: "powell", store: "Zumiez",
    brand: "Powell Peralta", price: "40", discount: "50", score: "10",
    starred: "0", fresh: "0", drop: "0", lowest: "0", added: "0", highlight: "0",
    dropday: "", soldout: "0", wheelbase: "", diameter: "", duros: "", shape: "",
    trucksize: "", truckheight: "", construction: "", abec: "", shoesize: "",
    prottype: "", protsize: ""
}};
assert.equal(rowMatches(row), true);
row.dataset.length = "30.0";
assert.equal(rowMatches(row), true);
row.dataset.length = "29.9";
assert.equal(rowMatches(row), false);
state.length = "30-31,31-32";
row.dataset.length = "31.75";
assert.equal(rowMatches(row), true);
""".replace("__BUCKETS__", json.dumps(buckets)).replace("__SOURCE__", source)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
            handle.write(script)
            path = handle.name
        result = subprocess.run(["node", path], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
