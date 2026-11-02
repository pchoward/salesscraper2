"""Dan's Comp-style BMX filters (sports/bmx/dans.py): Hub Type, Toptube Length,
Drive Side, Material and Color, read only from what the store states."""

import json
import unittest

import sports
from sports.bmx import dans, facets, stores


def offers_of(feed, store=None):
    kept = {}
    with sports.BMX.active():
        for scraper in stores.shopify.scrapers_for(store or stores.POWERS, stores.PARTS):
            for item in scraper.parse(json.dumps({"products": feed})):
                kept[item["name"]] = item
    return kept


class DansFieldTests(unittest.TestCase):
    def test_variants_state_top_tube_drive_side_and_colour(self):
        kept = offers_of([
            {"title": "Gateway Frame", "vendor": "Cult", "handle": "gateway", "product_type": "Frames",
             "options": [{"name": "Size"}, {"name": "Color"}], "variants": [
                 {"id": 1, "option1": "20.75\"", "option2": "Gloss Black", "price": "250", "compare_at_price": "350"},
                 {"id": 2, "option1": "21\"", "option2": "Raw", "price": "260", "compare_at_price": "350"},
                 {"id": 3, "option1": "20.5\"", "option2": "Red", "price": "350", "compare_at_price": "350"}]},
            {"title": "Clutch V2 Freecoaster Hub", "vendor": "Odyssey", "handle": "clutch", "product_type": "Hubs",
             "options": [{"name": "Drive"}], "variants": [
                 {"id": 4, "option1": "RSD", "price": "150", "compare_at_price": "190"},
                 {"id": 5, "option1": "LSD", "price": "155", "compare_at_price": "190"}]},
            {"title": "Black Ops Beartrap PC Pedals", "vendor": "Black Ops", "handle": "pedals", "product_type": "Pedals",
             "options": [{"name": "Options"}], "variants": [{"id": 6, "option1": "Purple", "price": "12", "compare_at_price": "20"}]},
        ])
        frame = kept["Cult Gateway Frame"]
        self.assertEqual([(o["variant_id"], o["specs"].get("top_tube"), o["specs"].get("color")) for o in frame["technical_offers"]],
                         [(1, ['20.75"'], ["Black"]), (2, ['21"'], ["Chrome / Polished"])],
                         "per variant; the full-price 20.5\" is not an offer")
        hub = kept["Odyssey Clutch V2 Freecoaster Hub"]
        self.assertEqual(hub["technical_specs"]["hub_type"], ["Freecoaster"])
        self.assertEqual([o["specs"]["drive_side"] for o in hub["technical_offers"]], [["Right (RHD)"], ["Left (LHD)"]])
        self.assertEqual([o["price"] for o in hub["technical_offers"]], [150.0, 155.0], "each side keeps its own price")
        pedals = kept["Black Ops Beartrap PC Pedals"]
        self.assertEqual(pedals["technical_specs"]["material"], ["Nylon / Plastic"])
        self.assertEqual(pedals["technical_specs"]["color"], ["Purple"], "colour from the variant, never 'Black' from the brand")

    def test_nothing_is_guessed(self):
        self.assertEqual(dans.listing_fields("Black Ops DefendR Fork", "Frames & Forks"), {}, "a brand is not a colour")
        self.assertEqual(dans.listing_fields("Cult Match Freecoaster Hub", "Seating"), {}, "hub type only where it applies")
        product = {"options": [{"name": "Size"}]}
        self.assertEqual(dans.variant_fields(product, {"option1": "20\""}, "Bikes"), {}, "a bike's 20\" is a wheel size")
        self.assertEqual(dans.variant_fields(product, {"option1": "20\""}, "Frames & Forks"), {}, "a bare 20 is ambiguous")
        self.assertEqual(dans.variant_fields(product, {"option1": "20.75\""}, "Frames & Forks"), {"top_tube": ['20.75"']})
        self.assertEqual(dans.variant_fields({"options": [{"name": "Top Tube Length"}]}, {"option1": "21"}, "Bikes"),
                         {"top_tube": ['21"']})
        self.assertEqual(dans.variant_fields(product, {"option1": "9.25\""}, "Steering"), {}, "a bar's rise is not a top tube")
        self.assertEqual(dans.listing_fields("S&M Chromoly Race XLT Bars", "Steering"), {"material": "Chromoly"})
        self.assertEqual(dans.listing_fields("Alienation Clash Full UD Carbon Rim", "Wheel Parts"), {"material": "Carbon"})

    def test_the_sidebar_offers_dans_filters(self):
        keys = [field["key"] for field in facets.FIELDS]
        for key in ("hub_type", "top_tube", "drive_side", "material", "color"):
            self.assertIn(key, keys)
        labels = {field["key"]: field["label"] for field in facets.FIELDS}
        self.assertEqual((labels["hub_type"], labels["top_tube"], labels["drive_side"]), ("Hub Type", "Toptube Length", "Drive Side"))
        params = [field["param"] for field in facets.FIELDS]
        self.assertEqual(len(params), len(set(params)), "URL keys are unique")


if __name__ == "__main__":
    unittest.main()
