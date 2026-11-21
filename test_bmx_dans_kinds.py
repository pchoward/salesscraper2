"""Dan's Comp filters by kind of part (owner, 2026-11-21)."""

import unittest

from sports.bmx import dans, facets


def product(options, values):
    return {"options": [{"name": name} for name in options],
            "variants": [dict((f"option{i + 1}", v) for i, v in enumerate(row)) for row in values]}


def variant_specs(kind, prod):
    found = {}
    for variant in prod["variants"]:
        for key, values in dans.kind_variant_fields(kind, prod, variant).items():
            found.setdefault(key, set()).update(values)
    return {key: sorted(values) for key, values in found.items()}


class KindVariantTests(unittest.TestCase):
    def test_size_option_means_what_the_kind_says(self):
        self.assertEqual(variant_specs("Sprockets", product(["Color", "Size"], [("Black", "25T"), ("Black", "28T")])),
                         {"teeth": ["25T", "28T"]})
        self.assertEqual(variant_specs("Sprockets", product(["Size"], [("37 3/8",), ("38 1/2",)])), {"teeth": ["37T", "38T"]})
        self.assertEqual(variant_specs("Cranks", product(["Color", "Size"], [("Chrome", "170mm"), ("Chrome", "175mm")])),
                         {"crank_length": ["170 mm", "175 mm"]})
        self.assertEqual(variant_specs("Tires", product(["Size"], [("20x2.35",), ("20x2.40",)])),
                         {"tire_width": ['2.35"', '2.4"']})
        self.assertEqual(variant_specs("Hubs", product(["Hub"], [("Front 8m 28h",), ("Front 20mm 36h",)])),
                         {"hub_holes": ["28H", "36H"]})
        self.assertEqual(variant_specs("Stems", product(["Reach", "Color"], [("48mm", "Black"), ("53mm", "Black")])),
                         {"stem_reach": ["48 mm", "53 mm"]})

    def test_other_kinds_ignore_the_size(self):
        self.assertEqual(variant_specs("Grips & Bar Ends", product(["Size"], [("170mm",)])), {})
        self.assertEqual(variant_specs("Stems", product(["Color"], [("48mm Black",)])), {})


class KindListingTests(unittest.TestCase):
    def test_titles(self):
        self.assertEqual(dans.kind_fields("Sprockets", "origin8 Alloy Chainring 110mm 5-bolt 52t"), {"teeth": ["52T"]})
        self.assertEqual(dans.kind_fields("Tires", "GT pool tire 20x2.30 Black/grey"), {"tire_width": ['2.3"']})
        self.assertEqual(dans.kind_fields("Seats", "Shadow Penumbra Railed Slim Seat"), {"seat_style": ["Railed"]})
        self.assertEqual(dans.kind_fields("Seats", "Salt Plus Pivotal Seat"), {"seat_style": ["Pivotal"]})
        self.assertEqual(dans.kind_fields("Stems", "Rant Trill Front Load Stem"), {"stem_type": ["Front load"]})
        self.assertEqual(dans.kind_fields("Hubs", "Profile Mini 36H Cassette Hub 9T Driver"),
                         {"hub_holes": ["36H"], "driver": ["9T"]})

    def test_description_only_when_it_names_one_value(self):
        self.assertEqual(dans.kind_fields("Forks", "Rant Twin Peaks 18\" Forks", "A 30mm offset for quick steering."),
                         {"fork_offset": ["30 mm"]})
        self.assertEqual(dans.kind_fields("Hubs", "Shadow Symbol Cassette Hub", "Available with a 9T driver or 10T driver."), {})
        self.assertEqual(dans.kind_fields("Seats", "Odyssey Seat", "Pivotal or railed versions."), {})
        self.assertEqual(dans.kind_fields("Seats", "Seatpost Rail Clamp"), {})

    def test_facets(self):
        keys = {f["key"]: f for f in facets.FIELDS}
        for key in ("teeth", "tire_width", "hub_holes", "driver", "seat_style", "stem_type", "stem_reach", "fork_offset"):
            self.assertIn(key, keys)
        self.assertEqual(keys["teeth"]["param"], "bmx_teeth")


if __name__ == "__main__":
    unittest.main()
