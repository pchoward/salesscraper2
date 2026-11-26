"""BMX spares get their own kind; tools and lubes show under Tools & Care (owner, 2026-11-26)."""

import unittest

from sports import headings
from sports.bmx import kinds


class Refine(unittest.TestCase):
    def test_spares_split_from_the_item(self):
        cases = [
            ("Forks", "Saltplus EX Fork Top Cap", "BMX Fork Top Caps", "Fork Parts"),
            ("Forks", "Stay Strong Reactiv 20\" Race Fork", "BMX Forks", "Forks"),
            ("Cranks", "Animal Akimbo Crank Spindle", "BMX Crank Spindles etc", "Crank Parts"),
            ("Cranks", "Odyssey Thunderbolt Cranks - RHD", "BMX Cranks", "Cranks"),
            ("Headsets", "Shadow Carbon Headset Spacers", "BMX Headset Spacers", "Headset Parts"),
            ("Headsets", "Billet BMX Deez Nuts 12 Point Threadless Headset Kit 1-1/8", "HEADSET", "Headsets"),
            ("Stems", "S&M Stem Bolts 6 Pack - Gold", "BMX Stems", "Stem Parts"),
            ("Pedals", "Eclat Contra Pedal Pin Set Black", "BMX Pedal Spares", "Pedal Parts"),
        ]
        for stored, name, kind, expected in cases:
            self.assertEqual(kinds.refine(stored, name, kind), expected, name)

    def test_brakes_split_like_the_bmx_shops(self):
        cases = [
            ("Odyssey Springfield Brake Kit", "BMX Brake Kits", "Brake Kits"),
            ("Stay Strong Regency U-Brake", "BMX Brakes", "Brakes"),
            ("Rant Spring II Brakes", "BMX Brakes", "Brakes"),
            ("Odyssey Monolever Medium", "BMX Brake Levers", "Brake Levers"),
            ("Odyssey Linear K-Shield Cable", "BMX Brake Cables", "Brake Cables"),
            ("Shadow Sano Brake Pads", "BMX Brake Pads", "Brake Pads"),
            ("Sunday Removable 990 Brake Mount - Single", "BMX Brake Mounts", "Brake Parts"),
            ("Odyssey Knarps Cable Ends", "BMX Brake Spares", "Brake Parts"),
        ]
        for name, kind, expected in cases:
            self.assertEqual(kinds.refine("Brakes & Accessories", name, kind), expected, name)

    def test_other_kinds_unchanged(self):
        self.assertEqual(kinds.refine("Hubs", "Profile Elite Cassette Hub", "BMX Rear Hubs"), "Hubs")
        self.assertIsNone(kinds.refine(None, "Thing"))


class Page(unittest.TestCase):
    def item(self, part, name, kind, product_type=""):
        return {"part": part, "name": name, "kind": kind, "product_type": product_type,
                "url": "https://shop.example/" + name,
                "technical_offers": [{"price": 5, "specs": {"kind": [kind]}}], "technical_specs": {"kind": [kind]}}

    def test_regroup_shows_the_refined_kind(self):
        data = {"k": [self.item("Frames & Forks", "Jet BMX Fork Top Cap Black / H24", "Forks", "BMX Forks")]}
        row = headings.regroup(data, "bmx")["k"][0]
        self.assertEqual(row["part"], "Frames & Forks")
        self.assertEqual(row["kind"], "Fork Parts")
        self.assertEqual(row["technical_offers"][0]["specs"]["kind"], ["Fork Parts"])
        self.assertEqual(data["k"][0]["kind"], "Forks")  # stored row unchanged

    def test_tools_and_care(self):
        for part, name in (("Drivetrain", "Odyssey Chain Breaker"), ("Drivetrain", "Park Tool PW-5 Home Mechanic Pedal Wrench"),
                           ("Tires", "Park Tool PPL-1 Polylube 1000 Grease - 4 oz. Tube"), ("Wheels", "Park Tool TS-2.3 Pro Wheel Truing Stand")):
            self.assertEqual(headings.heading("bmx", self.item(part, name, "Chains")), "Tools & Care", name)
        self.assertEqual(headings.heading("bmx", self.item("Drivetrain", "KMC Z410 Chain", "Chains")), "Drivetrain")
        self.assertEqual(headings.HEADINGS["bmx"][8], "Tools & Care")
        self.assertEqual(headings.HEADINGS["bmx"][9:], headings._gear("bmx"))

    def test_gear_untouched(self):
        lid = self.item("Protection", "Shadow Classic Helmet", "Helmets")
        self.assertEqual(headings.heading("bmx", lid), "Helmets")


if __name__ == "__main__":
    unittest.main()
