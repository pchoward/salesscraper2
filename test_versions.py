"""One listing per product per store (audit 2026-11-10)."""

import unittest

import sports
import versions


def item(url, price, was="100.00", **extra):
    return dict({"name": "Owliad Skateboard Deck", "url": url, "price_new": price, "price_old": was,
                 "part": "Decks", "store": "CCS", "image": url + ".jpg"}, **extra)


class VersionMergeTests(unittest.TestCase):
    def test_keeps_cheapest_and_lists_the_others(self):
        data = {"CCS_Decks": [item("https://shop.ccs.com/products/owliad-8-50", "60.00", width=8.5),
                              item("https://shop.ccs.com/products/owliad-8-25", "55.00", width=8.25),
                              dict(item("https://shop.ccs.com/products/other", "50.00"), name="Other Deck")]}
        away = versions.merge(data)
        names = [i["name"] for i in data["CCS_Decks"]]
        self.assertEqual(names, ["Owliad Skateboard Deck", "Other Deck"])
        kept = data["CCS_Decks"][0]
        self.assertEqual(kept["url"], "https://shop.ccs.com/products/owliad-8-25")
        self.assertEqual(kept["widths"], [8.25, 8.5])
        self.assertEqual([v["url"] for v in kept["versions"]], ["https://shop.ccs.com/products/owliad-8-50"])
        self.assertTrue(away["https://shop.ccs.com/products/owliad-8-50"].startswith("catalog scope: "))

    def test_spec_offers_and_sizes_combine(self):
        a = dict(item("https://x.com/products/a", "40.00"), part="Protection", name="Alpinestars Drop 6.0 Gloves",
                 technical_specs={"color": ["Blue"]}, protection_sizes=["M"])
        b = dict(item("https://x.com/products/b", "40.00"), part="Protection", name="Alpinestars Drop 6.0 Gloves",
                 technical_specs={"color": ["Black"]}, protection_sizes=["L"])
        with sports.MTB.active():
            kept, _ = versions.merge_items([a, b])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["technical_specs"]["color"], ["Blue", "Black"])
        self.assertEqual(kept[0]["protection_sizes"], ["M", "L"])
        self.assertEqual(a["technical_specs"]["color"], ["Blue"])  # inputs untouched

    def test_cheapest_under_ten_percent_does_not_hide_a_real_deal(self):
        weak = item("https://shop.ccs.com/products/owliad-a", "95.00")   # 5% off: filtered out
        good = item("https://shop.ccs.com/products/owliad-b", "120.00", was="200.00")
        kept, away = versions.merge_items([weak, good])
        self.assertEqual(len(kept), 2)
        self.assertEqual(away, {})

    def test_different_stores_and_parts_stay_apart(self):
        data = {"CCS_Decks": [item("https://shop.ccs.com/products/a", "55.00")],
                "TGM_Decks": [dict(item("https://tgm.com/products/a", "50.00"), store="TGM")]}
        self.assertEqual(versions.merge(data), {})


if __name__ == "__main__":
    unittest.main()
