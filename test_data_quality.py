"""PR B data quality (owner, 2026-11-03): one spelling per brand, and Skate
shops' protection shown in BMX. No network."""

import unittest

import sports
from sports import brands
from sports.bmx import stores


class BrandSpellingTests(unittest.TestCase):
    def test_spellings_merge(self):
        cases = {"bmx": {"187killerpads": "187 Killer Pads"},
                 "mtb": {"Fox Suspension": "Fox", "Stans": "Stan's NoTubes", "Schwalbe North America": "Schwalbe",
                         "Reserve Wheels": "Reserve", "Hope Tech": "Hope", "PNW": "PNW Components",
                         "Pro Components": "Pro", "Brooks England": "Brooks", "bernunlimited": "Bern"},
                 "ski": {"Bern Helmets": "Bern", "Dalbello Sports": "Dalbello", "Dragon Alliance": "Dragon",
                         "Phaenom Footwear": "Phaenom"}}
        for sport_id, spellings in cases.items():
            aliases = sports.get(sport_id).aliases_file()
            for vendor, brand in spellings.items():
                self.assertEqual(brands.canonical(vendor, aliases), brand, (sport_id, vendor))


class PadSetTests(unittest.TestCase):
    def test_a_three_pack_is_a_pad_set_only_when_it_is_pads(self):
        from sports.protection import protects
        self.assertEqual(protects("Jason Markk Quick Wipes 3 Pack"), [])
        self.assertEqual(protects("Stance Socks 3 Pack"), [])
        self.assertEqual(protects("Triple 8 Saver Series 3-Pack"), ["Pad Sets"])
        self.assertEqual(protects("187 Combo Pack Pads - Camo"), ["Pad Sets"])


class FakeSkateScraper:
    name, part, url, candidates = "TGM", "Protection", "https://tgm.example", 3

    def scrape(self):
        return [
            {"name": "Pro-Tec Classic Certified Helmet", "url": "u1", "price_new": "39.99", "price_old": "59.99",
             "part": "Protection", "store": "TGM", "prot_type": "helmet"},
            {"name": "Triple 8 Saver Series Pad Set", "url": "u2", "price_new": "29.99", "price_old": "44.99",
             "part": "Protection", "store": "TGM"},
            {"name": "Pro-Tec Classic Snow Helmet", "url": "u3", "price_new": "49.99", "price_old": "89.99",
             "part": "Protection", "store": "TGM"},
        ]


class SkateShopProtectionTests(unittest.TestCase):
    def test_bmx_reads_skate_shop_protection(self):
        wrapped = stores.SkateShopProtection(FakeSkateScraper())
        items = {i["name"]: i for i in wrapped.scrape()}
        self.assertEqual(set(items), {"Pro-Tec Classic Certified Helmet", "Triple 8 Saver Series Pad Set"},
                         "the snow helmet stays out")
        helmet = items["Pro-Tec Classic Certified Helmet"]
        self.assertEqual(helmet["technical_specs"]["protects"], ["Helmets"])
        self.assertEqual(helmet["kind"], "Helmets")
        self.assertNotIn("prot_type", helmet, "Skate's own fields are not carried over")
        self.assertEqual((wrapped.name, wrapped.part, wrapped.candidates), ("TGM", "Protection", 3))

    def test_wired_into_bmx(self):
        names = {s.name for s in stores.scrapers() if isinstance(s, stores.SkateShopProtection)}
        self.assertEqual(names, {"CCS", "Tactics", "TGM", "Deathgear", "Kinetic", "SPoT", "Exodus", "SoCal"})


if __name__ == "__main__":
    unittest.main()
