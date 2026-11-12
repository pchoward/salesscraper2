import re
import unittest

import report
import sports
from previews.publish import CategoryParser
from sports import headings


def _item(name, part, store="Shop", **extra):
    return dict({"name": name, "url": f"https://{store.lower()}.test/{abs(hash(name))}", "price_new": "60.00",
                 "price_old": "100.00", "part": part, "store": store}, **extra)


def _menu(html):
    parser = CategoryParser()
    parser.feed(html)
    return {entry["category"]: entry for entry in parser.categories.values()}


class HeadingTest(unittest.TestCase):
    def test_ski_protection_splits_into_goggles_and_body_armor(self):
        self.assertEqual(headings.heading("ski", _item("Smith 4D MAG Goggles", "Protection")), "Goggles")
        self.assertEqual(headings.heading("ski", _item("POC Spine VPD Back Protector", "Protection")), "Protection")
        self.assertEqual(headings.heading("ski", _item("Atomic Hawx Magna 130 S", "Boots")), "Boots")

    def test_bike_helmets_get_their_own_heading(self):
        self.assertEqual(headings.heading("mtb", _item("Fox Speedframe Pro MIPS Helmet", "Protection")), "Helmets")
        self.assertEqual(headings.heading("mtb", _item("Fox Launch Pro Knee Guards", "Protection")), "Protection")
        self.assertEqual(headings.heading("bmx", _item("Bell Sanction Full Face Helmet", "Protection")), "Helmets")
        self.assertEqual(headings.heading("bmx", _item("187 Pro Knee Pads", "Protection")), "Protection")
        # Same gear headings on every sport: Helmets, Goggles, Gloves, Protection.
        self.assertEqual(headings.heading("skate", _item("Triple 8 Gotham Helmet", "Protection")), "Helmets")
        self.assertEqual(headings.heading("mtb", _item("Fox Ranger Gloves", "Protection")), "Gloves")
        self.assertEqual(headings.heading("mtb", _item("100% Strata 2 Goggles", "Protection")), "Goggles")
        self.assertEqual(headings.heading("skate", _item("187 Pro Knee Pads", "Protection")), "Protection")
        for sport_id, menu in headings.HEADINGS.items():
            size = len(headings.GEAR)
            self.assertEqual(menu[-size:] if sport_id != "skate" else menu[-size - 1:-1], headings.GEAR, sport_id)

    def test_renames_and_merges(self):
        self.assertEqual(headings.heading("mtb", _item("RockShox ZEB", "Forks & Shocks")), "Suspension")
        self.assertEqual(headings.heading("bmx", _item("Profile Mini Cassette Hub", "Wheel Parts")), "Wheels & Hubs")
        self.assertEqual(headings.heading("bmx", _item("Odyssey Hazard Lite Wheel", "Wheels")), "Wheels & Hubs")
        self.assertEqual(headings.heading("bmx", _item("Odyssey Path Pro Tire", "Tires")), "Tires & Tubes")
        self.assertEqual(headings.heading("skate", _item("Baker Deck", "Decks")), "Decks")

    def test_regroup_copies_and_keeps_the_store_category(self):
        data = {"Shop_Protection": [_item("Smith Squad Goggles", "Protection")]}
        grouped = headings.regroup(data, "ski")
        self.assertEqual(grouped["Shop_Protection"][0]["part"], "Goggles")
        self.assertEqual(grouped["Shop_Protection"][0]["store_part"], "Protection")
        self.assertEqual(data["Shop_Protection"][0]["part"], "Protection")    # stored data unchanged
        self.assertIs(headings.regroup(data, "nosuch"), data)

    def test_every_alias_points_at_a_heading(self):
        for sport_id, aliases in headings.ALIASES.items():
            for target in aliases.values():
                self.assertIn(target, headings.HEADINGS[sport_id])

    def test_every_store_category_lands_on_a_heading(self):
        for sport_id, menu in headings.HEADINGS.items():
            for part in sports.SPORTS[sport_id].parts:
                self.assertIn(headings.heading(sport_id, {"name": "x helmet goggles", "part": part}), menu)


class PageTest(unittest.TestCase):
    def test_ski_page_menu(self):
        data = {"evo_Protection": [_item("Smith 4D MAG Goggles", "Protection", "evo"),
                                   _item("Oakley Flight Deck Goggles", "Protection", "evo"),
                                   _item("POC Spine VPD Back Protector", "Protection", "evo")],
                "evo_Boots": [_item("Atomic Hawx Magna 130 S Ski Boots", "Boots", "evo")]}
        html = report.build_report_html(data, {}, {}, set(), generated_at="2026-11-07T10:00:00+00:00", sport=sports.SKI)
        menu = _menu(html)
        self.assertEqual(menu["Goggles"]["count"], 2)
        self.assertEqual(menu["Protection"]["count"], 1)
        self.assertNotIn("Body Armor", menu)
        self.assertIn('"partAliases": {"body-armor": "Protection"}', html)

    def test_mtb_helmets_pass_the_catalog_rules_under_their_heading(self):
        # MTB's rules drop "BMX" words except in Protection; a BMX-style lid
        # sold for dirt jumping must stay when shown under Helmets.
        data = {"Shop_Protection": [_item("Bell Local BMX Helmet", "Protection")],
                "Shop_Forks & Shocks": [_item("RockShox ZEB Ultimate Fork", "Forks & Shocks")]}
        html = report.build_report_html(data, {}, {}, set(), generated_at="2026-11-07T10:00:00+00:00", sport=sports.MTB)
        menu = _menu(html)
        self.assertEqual(menu["Helmets"]["count"], 1)
        self.assertEqual(menu["Suspension"]["count"], 1)

    def test_skate_menu_order_and_names(self):
        data = {"Shop_Decks": [_item("Baker Brand Logo Deck 8.25", "Decks")],
                "Shop_Sneakers": [_item("Nike SB Dunk Low", "Sneakers")],
                "Shop_Completes": [_item("Element Complete Skateboard 8.0", "Completes")],
                "Shop_Protection": [_item("Triple 8 Gotham Helmet", "Protection"),
                                    _item("187 Pro Knee Pads", "Protection")]}
        html = report.build_report_html(data, {}, {}, set(), generated_at="2026-11-07T10:00:00+00:00")
        menu = _menu(html)
        order = [name for name, _ in sorted(menu.items(), key=lambda pair: pair[1]["order"])]
        self.assertEqual(order, ["all", "Decks", "Completes", "Helmets", "Protection", "Sneakers"])
        self.assertEqual(menu["Helmets"]["slug"], "helmets")
        self.assertEqual(menu["Sneakers"]["label"], "Shoes")          # the link stays type=sneaker
        self.assertEqual(menu["Sneakers"]["slug"], "sneaker")
        self.assertNotIn("label", menu["Decks"])
        self.assertTrue(re.search(r'data-part="Sneakers"[^>]*>\s*<span class="quick-name">Shoes</span>', html))


if __name__ == "__main__":
    unittest.main()
