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


if __name__ == "__main__":
    unittest.main()
