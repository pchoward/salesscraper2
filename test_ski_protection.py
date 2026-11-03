"""Ski Protection (owner, 2026-11-03): goggles, back protectors, vests, wrist
guards and impact shorts from every Ski store, next to Helmets."""

import unittest

from sports.ski import christy, stores, the_house


class SkiProtectionTests(unittest.TestCase):
    def test_each_store_maps_protection(self):
        self.assertEqual(stores.utah_part(["Category: Goggles"]), "Protection")
        self.assertIsNone(stores.utah_part(["Category: Gloves + Mittens"]), "gloves and mittens are warmth gear")
        self.assertEqual(stores.type_part("alpine helmets goggles goggles adult goggles"), "Protection")
        self.assertEqual(stores.type_part("alpine helmets goggles helmets race helmets"), "Helmets")
        self.assertEqual(stores.title_part("Uvex Scribble LG Junior Ski Goggle"), "Protection")
        self.assertIsNone(stores.title_part("Smith Lowdown Sunglasses"))
        self.assertEqual(stores.EVO.types["goggles"], "Protection")
        self.assertEqual(stores.EVO.types["armor"], "Protection")
        self.assertEqual(the_house.part_for({"subcategory": "goggles", "name": "Smith 4D MAG Goggles"}), "Protection")
        self.assertIsNone(the_house.part_for({"subcategory": "goggles", "name": "Smith 4D MAG Replacement Lens"}))
        self.assertEqual(the_house.part_for({"subcategory": "snowboard-accessories", "name": "Demon Impact Shorts"}), "Protection")
        self.assertIsNone(the_house.part_for({"subcategory": "snowboard-accessories", "name": "Dakine Stomp Pad"}))
        self.assertEqual(christy.part_for("POC Spine VPD Air Back Protector"), "Protection")
        self.assertEqual(christy.part_for("Oakley Flight Deck Goggles"), "Protection")

    def test_every_ski_store_scrapes_every_part(self):
        import sports
        self.assertEqual(stores.PARTS, sports.SKI.parts)
        self.assertEqual(the_house.PARTS, sports.SKI.parts)
        self.assertEqual(christy.PARTS, sports.SKI.parts)
        built = {(scraper.name.rsplit("_", 1)[0], scraper.part) for scraper in stores.scrapers()}
        for store in ("evo", "Utah Ski", "Gear West", "The House", "Christy Sports"):
            self.assertIn((store, "Protection"), built, store)


if __name__ == "__main__":
    unittest.main()
