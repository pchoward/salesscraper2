"""Deck and wheel colors from a variant field, else words in the title."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from page import COLOR_PALETTE, listing_color
from part_specs import MIN_SPEC_COUNT
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


class ColorParseTests(unittest.TestCase):
    def test_palette_and_explicit_color_beat_the_title(self):
        ids = [color_id for color_id, _label, _swatch in COLOR_PALETTE]
        self.assertEqual(
            ids,
            [
                "black-stain", "black", "white", "blue", "red", "green", "orange",
                "yellow", "pink", "purple", "natural", "clear", "multi",
            ],
        )
        stain = {"part": "Decks", "name": "Baker Logo Deck 8.25", "color": "Black Stain"}
        self.assertEqual(listing_color(stain), "black-stain")
        option = {
            "part": "Wheels",
            "name": "Spitfire Formula Four 54mm Black",
            "options": [{"name": "Color", "value": "White"}],
        }
        self.assertEqual(listing_color(option), "white")
        named = {
            "part": "Decks",
            "name": "Baker Logo Deck 8.25 Blue",
            "option1_name": "Color",
            "option1": "Red",
        }
        self.assertEqual(listing_color(named), "red")
        wood = {"part": "Decks", "name": "Trey Wood Deck 8.5", "color": "Wood"}
        self.assertEqual(listing_color(wood), "natural")

    def test_variant_code_then_title_words(self):
        coded = {
            "part": "Wheels",
            "name": "OJ Elite Mini Combo 101a Wheels",
            "url": "https://www.skatewarehouse.com/OJ/descpage-OJ.html?color=WH",
        }
        self.assertEqual(listing_color(coded), "white")
        # A code that is not on the palette does not invent a color.
        silver = {
            "part": "Wheels",
            "name": "Spitfire Formula Four 54mm 99a Wheels",
            "url": "https://www.skatewarehouse.com/x.html?color=SI",
        }
        self.assertEqual(listing_color(silver), "")
        # The code wins when it maps, even if the title says something else.
        override = {
            "part": "Wheels",
            "name": "Spitfire Black 54mm Wheels",
            "url": "https://www.skatewarehouse.com/x.html?color=WH",
        }
        self.assertEqual(listing_color(override), "white")

    def test_title_words_normalize_and_graphics_do_not(self):
        titles = {
            "Poorhouse Pop Deck - Black Stain 8.5x32.375": "black-stain",
            "Poorhouse Pop Deck - Blue Stain 8.5": "blue",
            "Baker Deck - Natural 8.125": "natural",
            "Spitfire 54mm 99a Natural Skateboard Wheels": "natural",
            "OJ 54mm 101a White Skateboard Wheels": "white",
            "Welcome Reyes Flail Green 9.0 Skateboard Deck": "green",
            "Deck - green/gold foil": "green",
            "Deck - red foil": "red",
            "Opera Deck - Yellow/Orange 9.0": "multi",
            "Spitfire Black & Blue Swirl 53mm Wheels": "multi",
            "OJ White & Gum 54mm Wheels": "white",
            "Deck - multi": "multi",
            "Deck - clear": "clear",
            "Deck - olive": "green",
            "There Beginnings Teal 8.06 Deck": "blue",
            "Zero Spellbound Black Dip 8.25 Deck": "black",
            "Opera Face Yellow Holographic Deck 8.0": "yellow",
            "Ritual Blue Egg Skateboard Deck 8.5": "blue",
        }
        for title, expected in titles.items():
            part = "Wheels" if "Wheels" in title else "Decks"
            self.assertEqual(listing_color({"part": part, "name": title}), expected, title)
        graphics = [
            "Flip Penny Toms Friends Purple Haze 8.25 Skateboard Deck",
            "Sk8mafia Turner Red Eye 8.25 Skateboard Deck",
            "Birdhouse Loy Big Red 8.5 Skateboard Deck",
            "Zero Burleigh Black Sheep 8.5 Skateboard Deck",
            "Powell Peralta Mike Frazier Yellow Man 2 9.5 Deck",
            "Krooked Cromer The Green Lady Deck 8.25",
            "Opera Trey Wood Digital Deck 9.0",
            "Hockey Stain Nowhere 8.38 Skateboard Deck",
            "Hockey Nik Stain Take Off Deck 8.44",
            "Bones Reds Skateboard Deck 8.0",
            "Baker Logo Deck 8.25",
        ]
        for title in graphics:
            self.assertEqual(listing_color({"part": "Decks", "name": title}), "", title)

    def test_photos_and_other_parts_are_not_a_color(self):
        self.assertEqual(listing_color({
            "part": "Decks",
            "name": "Baker Logo Deck 8.25",
            "image": "https://cdn.example.com/black-stain-blue-deck.jpg",
        }), "")
        self.assertEqual(listing_color({
            "part": "Sneakers",
            "name": "Nike SB Dunk Low White",
        }), "")
        self.assertEqual(listing_color({
            "part": "Bearings",
            "name": "Bones Reds Bearings",
        }), "")

    def test_section_follows_size_filters_and_counts_match(self):
        decks = []
        for index, name in enumerate(
            ["Black Stain", "Blue", "Blue", "Red", "Green", "White"]
        ):
            decks.append(_item(
                f"Baker Deck - {name} 8.25",
                "Decks",
                f"https://example.com/deck-{index}",
                wheelbase=14.25,
            ))
        decks.append(_item(
            "Baker Logo Deck 8.25",
            "Decks",
            "https://example.com/plain",
            wheelbase=14.25,
        ))
        wheels = [
            _item(
                f"Spitfire {color} 54mm 99a Skateboard Wheels",
                "Wheels",
                f"https://example.com/wheel-{index}",
            )
            for index, color in enumerate(["White", "White", "Black", "Natural", "Blue"])
        ]
        html = build_report_html(
            {"Zumiez_Decks": decks, "Zumiez_Wheels": wheels},
            {},
            generated_at="2026-10-11T21:46:35+00:00",
        )
        self.assertLess(html.index('data-section="wheelbase"'), html.index('data-section="deckcolor"'))
        self.assertLess(html.index('data-section="diameter"'), html.index('data-section="wheelcolor"'))
        self.assertIn('data-for="Decks"', html.split('data-section="deckcolor"', 1)[0][-80:] + html.split('data-section="deckcolor"', 1)[1][:80])
        self.assertIn('id="deckColorFilters"', html)
        self.assertIn('title="Black Stain"', html)
        self.assertIn('title="All colors"', html)
        blue = html.split('id="deckColorFilters"', 1)[1].split('data-value="blue"', 1)[1].split("</button>", 1)[0]
        self.assertIn('data-count="2"', blue)
        self.assertIn("swatch", blue)
        plain = next(row for row in html.split("<tr ") if "example.com/plain" in row)
        self.assertIn('data-color=""', plain)
        stained = next(row for row in html.split("<tr ") if "example.com/deck-0" in row)
        self.assertIn('data-color="black-stain"', stained)
        # Too few parsed colors and the section stays off.
        short = decks[: MIN_SPEC_COUNT - 1]
        short_html = build_report_html({"Zumiez_Decks": short}, {}, generated_at="2026-10-11T21:46:35+00:00")
        self.assertNotIn('data-section="deckcolor"', short_html)

    def test_a_blank_color_does_not_match_a_selection(self):
        source = (ROOT / "page.js").read_text(encoding="utf-8")
        script = r"""
const assert = require("node:assert/strict");
const document = { addEventListener() {} };
const window = {};
global.document = document;
global.window = window;
const LENGTH_BUCKETS = [];
const WHEELBASE_BUCKETS = [];
__SOURCE__
assert.deepEqual(normalizeColorParam("blue,nope,red"), ["blue", "red"]);
assert.deepEqual(normalizeColorParam("red,blue"), ["blue", "red"]);
state.part = "Decks";
state.colors = ["blue"];
const row = { dataset: {
    part: "Decks", length: "", size: "8.25", search: "baker", store: "Zumiez",
    brand: "Baker", price: "40", discount: "50", score: "10",
    starred: "0", fresh: "0", drop: "0", lowest: "0", added: "0", highlight: "0",
    dropday: "", soldout: "0", wheelbase: "", diameter: "", duros: "", shape: "",
    trucksize: "", truckheight: "", construction: "", abec: "", shoesize: "",
    prottype: "", protsize: "", color: "blue"
}};
assert.equal(rowMatches(row), true);
row.dataset.color = "";
assert.equal(rowMatches(row), false);
row.dataset.color = "red";
assert.equal(rowMatches(row), false);
state.colors = [];
row.dataset.color = "";
assert.equal(rowMatches(row), true);
state.part = "Wheels";
state.colors = ["white"];
row.dataset.part = "Wheels";
row.dataset.color = "white";
assert.equal(rowMatches(row), true);
""".replace("__SOURCE__", source)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
            handle.write(script)
            path = handle.name
        result = subprocess.run(["node", path], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
