import unittest

from sports.mtb import specs as mtb
from sports.ski import evo


def _mtb(name, part):
    found, _ = mtb.extract({"title": name}, {}, part)
    return found


class MtbNamesTest(unittest.TestCase):
    def test_drivetrain_speed(self):
        self.assertEqual(_mtb("SRAM GX Eagle 12-Speed Cassette", "Drivetrain")["speed"], ["12-speed"])
        self.assertEqual(_mtb("Shimano XTR M9120 1X 12sp Chainring 32T", "Drivetrain")["speed"], ["12-speed"])
        self.assertEqual(_mtb("Shimano Deore M6000 10sp Shadow Plus Rear Derailleur", "Drivetrain")["speed"], ["10-speed"])
        # One speed per family: Eagle, Shimano M8100 (12), M5100 (11).
        self.assertEqual(_mtb("SRAM X01 Eagle DUB 32T Boost Crankset", "Drivetrain")["speed"], ["12-speed"])
        self.assertEqual(_mtb("Shimano XT M8100 Rear Derailleur", "Drivetrain")["speed"], ["12-speed"])
        self.assertEqual(_mtb("Shimano Deore M5100 Shifter", "Drivetrain")["speed"], ["11-speed"])
        self.assertNotIn("speed", _mtb("SRAM eTap AXS Wireless Blips", "Drivetrain"))
        self.assertNotIn("speed", _mtb("Maxxis Minion 12-Speed? no", "Tires"))

    def test_tire_casing_and_tubeless(self):
        found = _mtb('Maxxis Minion DHF 29" x 2.5" - EXO+ - 3C MaxxTerra TR', "Tires")
        self.assertEqual(found["casing"], ["EXO+"])
        self.assertEqual(found["tubeless"], ["Tubeless ready"])
        self.assertEqual(_mtb("Maxxis Assegai 29 x 2.5 DoubleDown", "Tires")["casing"], ["DoubleDown"])
        self.assertEqual(_mtb("Schwalbe Magic Mary 29 x 2.4 Super Gravity Radial", "Tires")["casing"],
                         ["Radial", "Super Gravity"])
        # "DH Tire" is the store's word for the tire, not its casing; "DHF" is a model.
        self.assertNotIn("casing", _mtb('Maxxis Assegai 29" Folding DH Tire', "Tires"))
        self.assertEqual(_mtb('Maxxis Minion DHR II 29" Folding MTB Tire - WT - DH', "Tires")["casing"], ["DH"])
        # Inserts and sealant aren't tubeless tires.
        self.assertEqual(_mtb('Tannus Armour Tubeless Tire Insert - 29"', "Tires").get("tubeless"), None)

    def test_bare_wheel_size_on_forks_and_frames(self):
        self.assertEqual(_mtb("Fox 36 Float Factory 29 Fork", "Forks & Shocks")["wheel_size"], ["29"])
        self.assertEqual(_mtb("Santa Cruz Hightower 4 CC 29 Frame", "Frames")["wheel_size"], ["29"])
        self.assertNotIn("wheel_size", _mtb("Fox 36 Float 160mm 44mm Offset", "Forks & Shocks"))


class SkiNamesTest(unittest.TestCase):
    def test_boot_last_from_volume_in_the_name(self):
        self.assertEqual(evo.fields("Boots", "Lange Shadow 115 MV GW Ski Boots", "", [], "")["last"],
                         ["Medium (99–101 mm)"])
        self.assertEqual(evo.fields("Boots", "Tecnica Mach1 LV 95 W Ski Boots", "", [], "")["last"],
                         ["Narrow (98 mm and under)"])
        # A stated last wins over the name.
        self.assertEqual(evo.fields("Boots", "Tecnica Mach1 LV 130", "", [], "98mm last")["last"],
                         ["Narrow (98 mm and under)"])
        self.assertNotIn("last", evo.fields("Boots", "Atomic Hawx Magna 130 S", "", [], ""))

    def test_touring_boots_walk(self):
        self.assertEqual(evo.fields("Boots", "Atomic Hawx Prime XTD 130 BOA GW Alpine Touring Ski Boots", "", [], "")["walk"],
                         ["Walk mode"])
        self.assertNotIn("walk", evo.fields("Boots", "Nordica Speedmachine 3 130 GW", "", [], ""))

    def test_goggle_fit_and_lens(self):
        found = evo.fields("Protection", "Oakley Line Miner L Goggles 2026", "Goggles", [], "")
        self.assertEqual(found["goggle_size"], ["Large"])
        found = evo.fields("Protection", "Dragon RVX MAG OTG Goggles with Bonus Lens", "Goggles", [], "")
        self.assertEqual(found["goggle_fit"], ["Over glasses (OTG)"])
        self.assertEqual(found["goggle_lens"], ["Bonus lens included", "Magnetic lens change"])
        self.assertEqual(evo.fields("Protection", "Smith Squad Low Bridge Fit Goggles", "", [], "")["goggle_fit"],
                         ["Low bridge fit"])
        self.assertNotIn("goggle_size", evo.fields("Protection", "POC Spine VPD Back Protector L", "", [], ""))


if __name__ == "__main__":
    unittest.main()
