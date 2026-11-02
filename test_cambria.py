"""Cambria (issue #165): MTB parts from per-part sale collections whose types
name the discipline; wheel size and travel from its filter tags. No network."""

import json
import unittest

import sports
from sports.mtb import stores
from sports.mtb.rules import filter_reason


def product(id, title, vendor, kind, variants, tags=(), options=("Size",)):
    return {"id": id, "title": title, "vendor": vendor, "handle": f"p{id}", "product_type": kind,
            "tags": list(tags), "options": [{"name": n} for n in options], "variants": variants}


def variant(id, price="50.00", compare="80.00", available=True, **options):
    return {"id": id, "price": price, "compare_at_price": compare, "available": available, **options}


ALPAKA = product(1, "Eastern Alpaka 29 MTB Hardtail Bike - Gray", "Eastern", "Hardtail",
                 [variant(11, "549.99", "649.99", option1="Medium"), variant(12, "549.99", "649.99", option1="Large")],
                 tags=["Fforktravel_130mm", 'Fwheelsize_29"', "Fframesize_Medium", "Fframesize_Large"])
DUB = product(2, "SRAM DUB Threaded Bottom Bracket - BSA - 68/73mm", "SRAM", "MTB/Road Bottom Brackets", [variant(21, "39.99", "45.00")])
ULTEGRA = product(3, "Shimano Ultegra BBR60 Hollowtech II Bottom Bracket", "Shimano", "MTB/Road Bottom Brackets", [variant(31)])
SADDLE = product(4, "WTB Volt Saddle", "WTB", "Road & MTB Saddles", [variant(41)])
ROAD_BIKE = product(5, "Vaast Bikes R/1 700c Road Bike", "Vaast Bikes", "Road Bikes", [variant(51, "1499.99", "3199.00")])
BAG = product(6, "Topeak Saddle Bag", "Topeak", "Saddle Bags", [variant(61)])
WHEELS = product(7, "Stans Flow MK4 Wheelset", "Stans", "MTB Wheels",
                 [variant(71, option1='27.5"'), variant(72, option1='29"')],
                 tags=['Fwheelsize_27.5" (650b)', 'Fwheelsize_29"'])
CRUISER = product(9, "WheelMaster 24\" Alloy Cruiser/Comfort Wheel - Front", "WheelMaster", "Cruiser Wheels", [variant(91)])
CHAIR = product(10, "Sunlite Wheelchair Tire - Gray", "Sunlite", "Wheelchair Tires", [variant(101)])
TAPE = product(8, "Lizard Skins DSP Bar Tape", "Lizard Skins", "Handlebar Tape", [variant(81)])


def parse(products):
    kept = {}
    with sports.MTB.active():
        for scraper in [stores.MtbShopifyScraper(stores.CAMBRIA, part) for part in stores.PARTS]:
            for item in scraper.parse(json.dumps({"products": products})):
                kept[item["name"]] = item
    return kept


class CambriaTests(unittest.TestCase):
    def test_mountain_parts_only(self):
        kept = parse([ALPAKA, DUB, ULTEGRA, SADDLE, ROAD_BIKE, BAG, WHEELS, TAPE, CRUISER, CHAIR])
        self.assertEqual({name: item["part"] for name, item in kept.items()}, {
            "Eastern Alpaka 29 MTB Hardtail Bike - Gray": "Bikes",
            "SRAM DUB Threaded Bottom Bracket - BSA - 68/73mm": "Drivetrain",
            "WTB Volt Saddle": "Cockpit",
            "Stans Flow MK4 Wheelset": "Wheels",
        }, "shared MTB/Road types stay; road groupsets, road bikes, bags, bar tape, cruiser and wheelchair parts don't")

    def test_tagged_wheel_size_and_travel(self):
        kept = parse([ALPAKA, WHEELS])
        bike = kept["Eastern Alpaka 29 MTB Hardtail Bike - Gray"]
        self.assertEqual(bike["technical_specs"].get("travel_mm"), ["130"])
        self.assertEqual(bike["technical_specs"].get("wheel_size"), ["29"])
        self.assertEqual(bike["technical_specs"].get("frame_size"), ["L", "M"])
        offers = {o["variant_id"]: o["specs"].get("wheel_size") for o in kept["Stans Flow MK4 Wheelset"]["technical_offers"]}
        self.assertEqual(offers, {71: ["27.5"], 72: ["29"]}, "each variant gets only its own wheel size")

    def test_collections(self):
        self.assertEqual([url.split("/collections/")[1].split("/")[0] for url in stores.CAMBRIA.sale_jsons],
                         ["sale-components", "sale-frames-forks", "sale-wheels", "sale-tires", "sale-bikes"])

    def test_shared_type_rule(self):
        self.assertIsNone(filter_reason("Shimano XT Chain", "Drivetrain", product_type="MTB/Road Chains"))
        self.assertIsNotNone(filter_reason("Shimano 105 Chain", "Drivetrain", product_type="Road Chains"))
        self.assertIsNotNone(filter_reason("SRAM Rival AXS Derailleur", "Drivetrain", product_type="MTB/Road Derailleurs"))
        self.assertIsNone(filter_reason("SRAM Apex Eagle AXS Derailleur", "Drivetrain"), "Apex Eagle is an MTB group")
        self.assertIsNotNone(filter_reason("Soloist", "Bikes", product_type="BIKES AND FRAMES/BIKES - ROAD/PERFORMANCE ROAD"))


if __name__ == "__main__":
    unittest.main()
