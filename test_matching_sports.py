"""Cross-store matching for BMX, Ski and MTB (owner, 2026-11-06: "do this by
default at all sports"). Real pairs from the live catalogs; look-alikes that
are different products must stay apart."""

import unittest

import matching
import sports


def item(store, name, brand, part, price="100.00"):
    return {"store": store, "name": name, "brand": brand, "part": part, "price_new": price, "price_old": "200.00",
            "url": f"https://{store.replace(' ', '')}.example/{abs(hash(name))}"}


def together(left, right):
    return len(matching.sport_groups([left, right], apply_filters=False)) == 1


class SportMatchTests(unittest.TestCase):
    def test_real_pairs_match(self):
        pairs = [
            (item("Christy Sports", "Rossignol Sender Soul 102 Skis", "Rossignol", "Skis"),
             item("evo", "Rossignol Sender Soul 102 Skis 2026", "Rossignol", "Skis")),
            (item("The House", "K2 Anthem 95 BOA® Women's Ski Boots", "K2", "Boots"),
             item("evo", "K2 Anthem 95 BOA Ski Boots - Women's 2026", "K2", "Boots")),
            (item("Mike's Bikes", "Smith Forefront 3 MIPS", "Smith", "Protection"),
             item("Colorado Cyclist", "Smith Forefront 3 MIPS MTB Helmet - Matt Forest", "Smith", "Protection")),
            (item("Colorado Cyclist", "Maxxis High Roller III Tire - 29 x 2.4, Tubeless, Folding, Black, 3C MaxxGrip, EXO+",
                  "Maxxis", "Tires"),
             item("The Lost Co.", "Maxxis High Roller III - 29x2.4 - 3C MaxxGrip / EXO+", "Maxxis", "Tires")),
            (item("Albe's BMX", "Haro La Bastille Pivotal Seat", "Haro", "Seating"),
             item("Haro", "Haro La Bastille Pivotal Seat", "Haro", "Seating")),
        ]
        for left, right in pairs:
            self.assertTrue(together(left, right), (left["name"], right["name"]))

    def test_different_products_stay_apart(self):
        pairs = [
            ("Tecnica Mach BOA MV 100 Ski Boot 2026", "Tecnica Mach Boa MV 110 Ski Boots 2026", "Tecnica", "Boots"),
            ("Smith Vantage MIPS Helmet", "Smith Vantage 2 Mips Helmet 2026", "Smith", "Helmets"),
            ("Dragon DX3 OTG Goggles", "Dragon DX3 Plus OTG Goggles 2025", "Dragon", "Protection"),
            ("Atomic Savor Amid Helmet", "Atomic Savor GT Amid 2026", "Atomic", "Helmets"),
            ("Smith 4D MAG Goggles", "Smith I/O MAG XL Goggles", "Smith", "Protection"),
            ("Atomic Hawx Prime 120 S Ski Boots 2026", "Atomic Hawx Prime 120 S Ski Boots 2025", "Atomic", "Boots"),
            ("Atomic Hawx Prime 95 BOA Ski Boots", "Atomic Hawx Prime 95 BOA W Ski Boots - Women's", "Atomic", "Boots"),
            ("Atomic Hawx Ultra 85 Ski Boots", "Atomic Hawx Ultra 85 Ski Boots - Used", "Atomic", "Boots"),
            ("K2 Mindbender 90C Skis", "K2 Mindbender 90C Skis w/ Quikclick Bindings", "K2", "Skis"),
            ("Hayes Disc Brake Pads", "Hayes Dominion A4 Disc Brake", "Hayes", "Brakes"),
            ("SRAM Code RSC Disc Brake", "SRAM Code RSC Disc Brake Lever Assembly", "SRAM", "Brakes"),
            ("Schwalbe Magic Mary Tire - 27.5 x 2.4", "Schwalbe Magic Mary - 29x2.4", "Schwalbe", "Tires"),
            ("Maxxis High Roller III Tire - 29 x 2.4, Tubeless, Folding, Black, 3C MaxxGrip, DH",
             "Maxxis High Roller III - 29x2.4 - 3C MaxxGrip / EXO+", "Maxxis", "Tires"),
            ("7iDP Flex Knee", "7 iDP Flex Adult Elbow/Youth Knee Pad", "7iDP", "Protection"),
        ]
        for left, right, brand, part in pairs:
            self.assertFalse(together(item("A Shop", left, brand, part), item("B Shop", right, brand, part)), (left, right))

    def test_a_vague_name_never_chains_two_products(self):
        items = [item("A", "Giro Source MIPS Helmet", "Giro", "Protection"),
                 item("B", "Giro Source MIPS Helmet - Black", "Giro", "Protection"),
                 item("C", "Giro Source MIPS Helmet - Women's", "Giro", "Protection")]
        groups = matching.sport_groups(items, apply_filters=False)
        self.assertEqual([sorted(o["store"] for o in g["offers"]) for g in groups], [["A", "B"]])

    def test_cross_store_groups_uses_the_sport(self):
        pair = [item("Christy Sports", "Volkl M7 Mantra Skis", "Volkl", "Skis"),
                item("evo", "Volkl M7 Mantra Skis 2026", "Volkl", "Skis")]
        self.assertEqual(len(matching.cross_store_groups(pair, apply_filters=False, sport=sports.SKI)), 1)
        self.assertEqual(matching.cross_store_groups(pair, apply_filters=False), [], "Skate's rules by default")


if __name__ == "__main__":
    unittest.main()
