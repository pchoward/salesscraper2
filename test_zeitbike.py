import unittest

import sports
from sports import zeitbike
from stores import shopify

SKATE_PADS = ["Category_Brands/TSG", "Category_Products/Pads (Skate)", "activity_skating"]
BIKE_PADS = ["Category_Brands/TSG", "Category_Products/Pads (Bike)"]
SKATE_LID = ["Category_Brands/TSG", "Category_Products/Helmets (Bike)", "Category_Products/Helmets (Skate)"]
TRAIL_LID = ["Category_Brands/TSG", "Category_Products/Helmets (Bike)"]
SNOW_LID = ["Category_Brands/TSG", "Category_Products/Helmets (Snow)", "activity_snowboarding"]


class PartTest(unittest.TestCase):
    def test_pads_go_where_zeitbike_files_them(self):
        knee = ("Protective Pads", "TSG - Kneeguard Force V A", SKATE_PADS)
        self.assertEqual(zeitbike.part("skate", *knee), "Protection")
        self.assertEqual(zeitbike.part("bmx", *knee), "Protection")
        self.assertIsNone(zeitbike.part("mtb", *knee))
        bike = ("Protective Pads", "TSG - Kneesleeve Tahure A", BIKE_PADS)
        self.assertIsNone(zeitbike.part("skate", *bike))
        self.assertEqual(zeitbike.part("mtb", *bike), "Protection")

    def test_helmets_by_sport(self):
        lid = ("Helmets", "TSG - Evolution Helmet", SKATE_LID)
        self.assertEqual(zeitbike.part("skate", *lid), "Protection")
        self.assertEqual(zeitbike.part("mtb", *lid), "Protection")
        trail = ("Helmets", "TSG - Helmet - Scope Solid Color - Satin Black", TRAIL_LID)
        self.assertIsNone(zeitbike.part("skate", *trail))
        self.assertIsNone(zeitbike.part("bmx", *trail))     # trail lids aren't BMX
        full_face = ("Helmets", "TSG - Sentinel Helmet - Full Face Downhill MTB", TRAIL_LID)
        self.assertEqual(zeitbike.part("bmx", *full_face), "Protection")
        self.assertIsNone(zeitbike.part("skate", *full_face))
        snow = ("Helmets", "TSG - Ski/Snowboard Helmet - Gravity", SNOW_LID)
        self.assertEqual(zeitbike.part("ski", *snow), "Helmets")
        self.assertIsNone(zeitbike.part("skate", *snow))

    def test_goggles_on_ski_only(self):
        goggle = ("Eyewear", "TSG - Winter Goggle - Goggle Four - One Size", ["activity_snowboarding"])
        self.assertEqual(zeitbike.part("ski", *goggle), "Protection")
        self.assertIsNone(zeitbike.part("ski", "Eyewear", "TSG - Winter Goggle Accessories - Replacement Lens Goggle One",
                                        ["activity_snowboarding"]))

    def test_spares_and_shop_displays_stay_out(self):
        for kind, title, tags in (
                ("Protective Spareparts", "TSG - Pass 2.0 Cheek Pad Set", ["Category_Products/Pads (Skate)"]),
                ("Protective Pads", "TSG - Recaps Force III /II (Skate Knee Pad Replacement)", SKATE_PADS),
                ("Helmet Rack", "TSG - Sales Support - Basic Steel Display for Helmets", ["model_sales-support", "tsg"]),
                ("Protective Pads", "TSG - Adult Helmet Pad Kit HS", SKATE_PADS)):
            for sport_id in ("skate", "bmx", "mtb", "ski"):
                self.assertIsNone(zeitbike.part(sport_id, kind, title, tags), (sport_id, title))


class StoreTest(unittest.TestCase):
    def test_product_part_decides_alone(self):
        store = zeitbike.store(sports.SKATE)
        self.assertEqual(store.store, "Zeitbike")
        self.assertEqual(shopify.part_for(store, "Protective Pads", "TSG - Kneeguard Force V A", SKATE_PADS), "Protection")
        self.assertIsNone(shopify.part_for(store, "Protective Pads", "TSG - Kneesleeve Tahure A", BIKE_PADS))

    def test_mtb_reads_newmen_by_type(self):
        from sports.mtb import stores as mtb
        store = mtb.ZEITBIKE
        self.assertEqual(store.sale_jsons[1], "https://www.zeitbike.com/collections/newmen-components/products.json")
        self.assertEqual(shopify.part_for(store, "Wheels", "NEWMEN Front Wheel - Forge 30 base 29\"", ["NEWMEN"]), "Wheels")
        self.assertEqual(shopify.part_for(store, "Stems", "NEWMEN Stem - Advanced SL 318.4", []), "Cockpit")

    def test_registered_on_every_sport(self):
        from sports.bmx import stores as bmx
        from sports.ski import stores as ski
        from stores import protection_brands
        for stores in (protection_brands.STORES, bmx.BRAND_STORES, ski.BRAND_STORES):
            self.assertIn("Zeitbike", [store.store for store in stores])


if __name__ == "__main__":
    unittest.main()
