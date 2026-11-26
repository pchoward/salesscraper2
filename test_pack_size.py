"""Pack size filter on every sport's Packs (owner, 2026-11-25: "add size when
it's available, many are 28L, smaller or larger")."""

import unittest

import sports
from sports import packs
from sports.facets import payload


class VolumeTests(unittest.TestCase):
    def test_litres_in_the_title(self):
        cases = {
            "Dakine Heli Pro 20L Backpack": 20,
            "Herschel Supply Co. All Season 29 L Backpack": 29,
            "Mountain Hardwear Field Day™ 28L Backpack": 28,
            "Ortovox Cross Rider 20L S Backpack": 20,
            "Burton Prospect 2.0 20L Backpack": 20,
            "Dakine Session 8L Hydration Pack": 8,
        }
        for name, litres in cases.items():
            self.assertEqual(packs.volume_litres(name), litres, name)

    def test_the_reservoir_is_not_the_pack(self):
        self.assertEqual(packs.volume_litres("CamelBak M.U.L.E. 12L Hydration Pack with 3L Reservoir"), 12)
        self.assertEqual(packs.volume_litres("Osprey Raptor 14 Pack + 2.5L Reservoir"), 14)
        self.assertIsNone(packs.volume_litres("USWE Outlander XC 2L Hydration Pack"))  # under 4L: a reservoir size
        self.assertIsNone(packs.volume_litres("EVOC Hydro Pro 3 + 1.5l Bladder"))

    def test_brands_that_name_the_litres(self):
        cases = {
            "Osprey Sopris 32 Backpack": 32,
            "Osprey Soelden Pro E2 Airbag Pack 32 Backpack": 32,
            "Osprey Seral 7 Lumbar Pack": 7,
            "Osprey Kamber 22 In-Line Pack": 22,
            "CamelBak M.U.L.E. 12 100oz Hydration Pack - Women's": 12,
            "CamelBak Chase Adventure 8 Vest 70oz Hydration Pack": 8,
            "EVOC Stage 6 + 2L Bladder": 6,
            "Deuter Trans Alpine 30 Backpack": 30,
            "Gregory Targhee 32 Backpack - 2024": 32,
        }
        for name, litres in cases.items():
            self.assertEqual(packs.volume_litres(name), litres, name)
        self.assertIsNone(packs.volume_litres("CamelBak Mini M.U.L.E. 50oz Hydration Pack - Kids'"))
        self.assertIsNone(packs.volume_litres("Vans Divert Backpack - black"))  # not a litre-named brand

    def test_unclear_stays_unknown(self):
        self.assertIsNone(packs.volume_litres("Evoc FR Trail 20L S/M 22L M/L Protector Pack"))
        self.assertIsNone(packs.volume_litres("Nike SB Heritage 2.0 Backpack"))
        self.assertEqual(packs.volume_litres("Dickies Basic Backpack", "Capacity: 22L. Laptop sleeve."), 22)
        self.assertEqual(packs.volume_litres("Dakine 18L Pack", "Fits 2L reservoir, 24L expanded"), 18)

    def test_sizes(self):
        self.assertEqual([packs.volume_size(v) for v in (8, 14.5, 15, 24, 25, 28, 34, 35, 45, None)],
                         ["Under 15L", "Under 15L", "15–24L", "15–24L", "25–34L", "25–34L", "25–34L", "35L+",
                          "35L+", None])


class FilterTests(unittest.TestCase):
    def test_every_sport_but_skate_has_it(self):
        for sport_id in ("bmx", "ski", "mtb"):
            module = __import__(f"sports.{sport_id}.facets", fromlist=["FIELDS"])
            field = next(f for f in module.FIELDS if f["key"] == "pack_volume")
            self.assertEqual(field["categories"], ("Packs",))
            self.assertEqual(field["param"], f"{sport_id}_packsize")
            self.assertEqual(len({f["param"] for f in module.FIELDS}), len(module.FIELDS))

    def test_packs_without_spec_data_join(self):
        # A skate shop's pack pooled onto BMX has no technical_offers.
        pooled = {"Tactics_Packs": [
            {"name": "Dakine Mission 25L Backpack", "url": "https://t.example/mission", "part": "Packs",
             "store": "Tactics", "price_new": "59.95", "price_old": "84.95"},
            {"name": "Vans Divert Backpack", "url": "https://t.example/divert", "part": "Packs", "store": "Tactics",
             "price_new": "29.95", "price_old": "45.00"},
        ], "Evo_Packs": [
            {"name": "Osprey Sopris 32 Backpack", "url": "https://e.example/sopris", "part": "Packs", "store": "evo",
             "price_new": "150.00", "price_old": "200.00",
             "technical_offers": [{"price": 150.0, "compare": 200.0, "available": True, "specs": {"gender": ["Women's"]}}]},
        ]}
        sport = sports.SPORTS["bmx"]
        with sport.session():
            config = payload(pooled, sport)
        items = config["items"]
        mission = items["https://t.example/mission"]["offers"][0]
        self.assertEqual(mission["specs"], {"pack_volume": ["25–34L"]})
        self.assertEqual((mission["price"], mission["compare"]), (59.95, 84.95))  # price and % ranges still work
        self.assertNotIn("https://t.example/divert", items)  # no size, no spec data: unchanged
        sopris = items["https://e.example/sopris"]["offers"][0]["specs"]
        self.assertEqual(sopris, {"gender": ["Women's"], "pack_volume": ["25–34L"]})
        field = next(f for f in config["fields"] if f["key"] == "pack_volume")
        self.assertEqual(field["values"], ["25–34L"])
        self.assertNotIn("pack_volume", pooled["Evo_Packs"][0]["technical_offers"][0]["specs"])  # stored data unchanged


if __name__ == "__main__":
    unittest.main()
