"""One spelling per brand on BMX/Ski/MTB (owner, 2026-11-04: 187, Pro-Tec and
Triple 8 still showed under two names)."""

import unittest

import sports
from sports import brands


class FromTitleTests(unittest.TestCase):
    def test_brand_from_the_start_of_the_name(self):
        bmx, mtb = sports.BMX.aliases_file(), sports.MTB.aliases_file()
        cases = [(bmx, "187 Combo Pack Pads - Camo", "187 Killer Pads"),
                 (bmx, "Pro-Tec Old School Low Pro Helmet", "Pro-Tec"),
                 (bmx, "Triple Eight Deep Cover Helmet", "Triple 8"),
                 (bmx, "S-One Lifer Helmet", "S-One"),
                 (bmx, "Profile Racing Hub", "Profile"),
                 (mtb, "Pro Koryak Dropper Seatpost", "Pro"),
                 (mtb, "KS Suspension Crux Integra Dropper", "KS"),
                 (bmx, "Jason Markk Wipes", "")]
        for path, name, brand in cases:
            self.assertEqual(brands.from_title(name, path), brand, name)

    def test_settle_fills_and_canonicalises(self):
        items = [{"name": "Triple Eight Deep Cover Helmet"}, {"name": "Bike Bumsaver", "brand": "triple eight"},
                 {"name": "Unknown Thing"}]
        brands.settle(items, sports.BMX.aliases_file())
        self.assertEqual([i.get("brand") for i in items], ["Triple 8", "Triple 8", None])

    def test_scraper_settles_new_sports_only(self):
        from pathlib import Path
        text = (Path(__file__).resolve().parent / "scraper.py").read_text(encoding="utf-8")
        self.assertIn("if not sport.is_default:", text.split("run_stores(scrapers)", 1)[1][:400])
        self.assertIn("brands.settle(items, sport.aliases_file())", text)


class SkateBrandTests(unittest.TestCase):
    """The Skate page (owner, 2026-11-04: 187 / 187killerpads, Pro, Triple)."""

    def test_protection_brands_get_one_spelling(self):
        import page
        cases = [({"name": "187 Combo Pack Pads - Camo", "part": "Protection"}, "187 Killer Pads"),
                 ({"name": "187killerpads ELBOW PAD", "brand": "187killerpads"}, "187 Killer Pads"),
                 ({"name": "Pro Tec Gasket Elbow Pads", "part": "Protection"}, "Pro-Tec"),
                 ({"name": "Pro-Tec Classic Helmet", "part": "Protection"}, "Pro-Tec"),
                 ({"name": "Triple Eight Deep Cover Helmet", "part": "Protection"}, "Triple 8"),
                 ({"name": "Pads", "brand": "Demon United"}, "Demon"),
                 ({"name": "Baker Brand Logo Deck", "part": "Decks", "brand": "Baker"}, "Baker"),
                 ({"name": "Spitfire Formula Four Wheels", "part": "Wheels"}, "Spitfire")]
        for item, brand in cases:
            self.assertEqual(page.deal_brand(item), brand, item["name"])

    def test_skate_warehouse_badge_is_not_part_of_the_name(self):
        from stores.skatewarehouse import _drop_badge
        self.assertEqual(_drop_badge("Best SellerTriple 8 Saver Series"), "Triple 8 Saver Series")
        for name in ("Salem Deck", "Newport Shoe", "Best Seller Pads"):
            self.assertEqual(_drop_badge(name), name)


if __name__ == "__main__":
    unittest.main()
