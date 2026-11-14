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

    def test_pool_shares_packs_where_they_belong(self):
        """Owner, 2026-11-14: no ski packs on BMX or Skate. Snow packs go to
        Ski, bike packs to MTB, a sport's own brand to that sport; everyday
        packs go to the tabs of their store's family (skate+BMX, ski+MTB)."""
        def item(name, url, part="Packs", kind="", brand=""):
            return {"name": name, "url": url, "part": part, "product_type": kind, "brand": brand,
                    "price_new": "30", "price_old": "50", "store": "x"}
        catalogs = {
            "ski": {"evo_Packs": [item("Dakine Heli Pro 20L Backpack", "https://evo/heli", kind="Ski Snowboard Backpacks"),
                                  item("CamelBak M.U.L.E. 12 Hydration Pack", "https://evo/mule", kind="Hydration Packs"),
                                  item("Topo Designs Rover Classic Backpack", "https://evo/topo", kind="Day Packs"),
                                  item("Hurley Printed Standard Backpack Beach Chair", "https://evo/chair")],
                    "evo_Skis": [item("Line Pandora 94", "https://evo/ski", "Skis")]},
            "skate": {"Zumiez_Packs": [item("Jansport Superbreak Plus Backpack", "https://zumiez/jansport"),
                                       item("Spitfire Bighead Backpack", "https://zumiez/spitfire")],
                      "Tactics_Packs": [item("DAKINE Women's Heli 12L Backpack - pinebark", "https://tactics/heli")]},
            "mtb": {"EVOC_Packs": [item("EVOC RIDE 12", "https://evoc/ride", kind="Hydration Bags", brand="EVOC")]},
            "bmx": {"Source BMX US_Packs": [item("Shadow Conspiracy Session Backpack", "https://source/shadow")]},
        }
        load = lambda sport: catalogs[sport.id]
        def urls(sport_id):
            pooled = packs.pool(catalogs[sport_id], sport_id, load=load)
            return sorted(i["url"] for items in pooled.values() for i in items if i.get("part") == "Packs")
        self.assertEqual(urls("bmx"), ["https://source/shadow", "https://zumiez/jansport"])
        self.assertEqual(urls("skate"), ["https://zumiez/jansport", "https://zumiez/spitfire"])
        self.assertEqual(urls("ski"), ["https://evo/heli", "https://evo/topo", "https://tactics/heli"])
        self.assertEqual(urls("mtb"), ["https://evo/mule", "https://evo/topo", "https://evoc/ride"])
        pooled = packs.pool(catalogs["mtb"], "mtb", load=load)
        self.assertEqual(pooled["evo_Packs"][0]["pooled_from"], "ski")
        self.assertNotIn("evo_Skis", pooled)
        self.assertEqual(len(catalogs["ski"]["evo_Packs"]), 4)  # stored data untouched
        self.assertEqual(packs.pool(pooled, "mtb", load=load), pooled)

    def test_pack_homes(self):
        cases = {("Ortovox Switchback 27L Backpack", "Ski Snowboard Backpacks"): "ski",
                 ("Dakine Poacher RAS Vest / Backpack - black", ""): "ski",
                 ("Osprey Seral 7 Lumbar Pack", "Fanny Packs"): "mtb",
                 ("Dakine Hot Laps 5L Hip Pack", ""): "mtb",
                 ("EVOC Mission", "Backpacks"): "mtb",
                 ("Herschel Supply Co. Classic XL Black Backpack", ""): None,
                 ("Burton Day Hiker 22L Pack", ""): None,
                 ("Vans Old Skool Backpack", ""): None}
        for (name, kind), home in cases.items():
            self.assertEqual(packs.home(name, "", kind), home, name)

    def test_junk_dropped_when_built(self):
        for name in ("Discmania Disc Golf Bag Fanatic Go Backpack", "2020 Rant Sticker Pack",
                     "100% Racecraft 2 / Accuri 2 / Strata 2 Tear-Offs 2x7 laminated pack", "Shadow Obscura Camera Bag",
                     "Fit Louis Bumbag", "CamelBak Quick Stow 17oz Flask", "Herschel Supply Co. Nova Crossbody"):
            self.assertFalse(packs.shown_on({"part": "Packs", "name": name}, "bmx"), name)
        # Real packs whose names mention a bladder or pouch stay.
        for name in ("EVOC Hydro Pro 3 + 1.5l Bladder", "EVOC Hip Pouch Pro + Drink Bottle"):
            self.assertTrue(packs.shown_on({"part": "Packs", "name": name, "brand": "EVOC"}, "mtb"), name)
        self.assertTrue(packs.shown_on({"part": "Decks", "name": "Sticker deck"}, "skate"))


if __name__ == "__main__":
    unittest.main()
