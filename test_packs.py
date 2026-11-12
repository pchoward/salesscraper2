"""Packs on every sport (owner, 2026-11-12): backpacks and hydration packs."""

import unittest

import sports
from filters import filter_reason
from sports import headings, packs
from stores import shopify


class PackTests(unittest.TestCase):
    def test_what_is_a_pack(self):
        for name in ("Dakine Heli Pro 20L Backpack", "CamelBak M.U.L.E. 12 Hydration Pack", "EVOC Hip Pack Pro 3L",
                     "Salomon Trailblazer 20 Daypack", "Dakine Heli Pro 20L Pack",
                     "Black Diamond JetForce Pro 25L Avalanche Airbag Pack", "BCA Float 32 Avalanche Airbag 2.0"):
            self.assertTrue(packs.is_pack(name), name)
        for name in ("Triple 8 Saver Series Pad Set (3-Pack)", "Thrasher Sticker Pack", "Dakine Boot Locker 69L Bag",
                     "Burton Wheelie Gig Bag 130cm", "Topeak Wedge Saddle Bag", "Odyssey Slugger duffel bag",
                     "CamelBak Crux 3L Reservoir", "187 Killer Pads Six Pack Pad Set", "Dakine Hot Laps Fanny Pack"):
            self.assertFalse(packs.is_pack(name), name)
        self.assertTrue(packs.is_pack("Odyssey Switch Pack - navy", "", ["Backpacks", "Odyssey"]))
        self.assertTrue(packs.is_pack("BCA Float 32", "Airbags"))

    def test_whose_pack(self):
        self.assertEqual(packs.sport_of("Shadow Conspiracy Session Backpack"), "bmx")
        self.assertEqual(packs.sport_of("Spitfire Bighead Backpack"), "skate")
        self.assertEqual(packs.sport_of("Thrasher Flame Backpack"), "skate")
        self.assertEqual(packs.sport_of("Mammut Free 28 Airbag 3.0 Backpack"), "ski")
        for name in ("Dakine Heli Pro 20L Backpack", "CamelBak M.U.L.E. 12 Hydration Pack",
                     "Santa Cruz Classic Dot Backpack", "Vans Obstacle Backpack"):
            self.assertIsNone(packs.sport_of(name), name)

    def test_every_sport_has_packs_after_protection(self):
        for sport in sports.SPORTS.values():
            self.assertIn("Packs", sport.parts, sport.id)
        self.assertEqual(headings.GEAR[-2:], ("Protection", "Packs"))
        self.assertIn("Packs", shopify.ALL_PARTS)

    def test_rules_keep_sport_brands_home(self):
        cases = {"Shadow Conspiracy Session Backpack": "bmx", "Spitfire Bighead Backpack": "skate",
                 "Black Diamond JetForce Pro 25L Avalanche Airbag Pack": "ski"}
        for sport in sports.SPORTS.values():
            with sport.active():
                for name, home in cases.items():
                    reason = filter_reason(name, "Packs", "", "30", "50")
                    self.assertEqual(reason is None, sport.id == home, (sport.id, name, reason))
                self.assertIsNone(filter_reason("CamelBak M.U.L.E. 12 Bike Hydration Pack", "Packs", "", "30", "50"),
                                  sport.id)
                self.assertIsNone(filter_reason("Dakine Hydration Vest 8L", "Packs", "", "30", "50"), sport.id)

    def test_shopify_sorts_packs_first(self):
        store = shopify.ShopifyStore("Test", "Test", "https://example.com", types={"bags": "Accessories"})
        self.assertEqual(shopify.part_for(store, "Bags", "Dakine Mission 25L Backpack"), "Packs")
        self.assertEqual(shopify.part_for(store, "Bags", "Dakine Boot Locker 69L Bag"), "Accessories")

    def test_pool_adds_other_sports_general_packs_once(self):
        def item(name, url, part="Packs"):
            return {"name": name, "url": url, "part": part, "price_new": "30", "price_old": "50", "store": "evo"}
        catalogs = {
            "ski": {"evo_Packs": [item("Dakine Heli Pro 20L Backpack", "https://evo/heli"),
                                  item("Mammut Free 28 Airbag 3.0 Backpack", "https://evo/mammut")],
                    "evo_Skis": [item("Line Pandora 94", "https://evo/ski", "Skis")]},
            "skate": {"Exodus_Packs": [item("Spitfire Bighead Backpack", "https://exodus/spitfire")]},
            "mtb": {"Mike's Bikes_Packs": [item("CamelBak M.U.L.E. 12 Hydration Pack", "https://mikes/mule")]},
            "bmx": {},
        }
        own = {"Source BMX US_Packs": [item("Shadow Conspiracy Session Backpack", "https://source/shadow")],
               "Source BMX US_Tires": [item("Shadow Valor Tire", "https://source/tire", "Tires")]}
        pooled = packs.pool(own, "bmx", load=lambda sport: catalogs[sport.id])
        urls = sorted(i["url"] for items in pooled.values() for i in items if i.get("part") == "Packs")
        self.assertEqual(urls, ["https://evo/heli", "https://mikes/mule", "https://source/shadow"])
        self.assertEqual(pooled["evo_Packs"][0]["pooled_from"], "ski")
        self.assertNotIn("evo_Skis", pooled)
        self.assertEqual(len(own["Source BMX US_Packs"]), 1)  # input untouched
        self.assertEqual(packs.pool(pooled, "bmx", load=lambda sport: catalogs[sport.id]), pooled)


if __name__ == "__main__":
    unittest.main()
