"""Name parsing for type-specific filters, and when those sections render."""

import json
import unittest

from dimensions import extract_specs
from report import build_report_html
from part_specs import (
    MIN_SPEC_COUNT,
    bearing_specs,
    diameter_band,
    section_ready,
    truck_specs,
    wheel_specs,
)
from query_state import decode_query, encode_state


def _item(name, part, url, store="Zumiez"):
    return {
        "name": name,
        "url": url,
        "price_new": "40.00",
        "price_old": "80.00",
        "part": part,
        "store": store,
    }


class WheelSpecTests(unittest.TestCase):
    def test_explicit_mm_and_half_open_bands(self):
        parsed = wheel_specs("Spitfire Diego Rude Awakening Formula Four 55.5mm 99a White Skateboard Wheels")
        self.assertEqual(parsed["diameter_mm"], 55.5)
        self.assertEqual(parsed["durometers"], ["99a"])
        self.assertEqual(diameter_band(55.5), "54-55")
        self.assertEqual(diameter_band(50), "50-51")
        self.assertEqual(diameter_band(51.9), "50-51")
        self.assertEqual(diameter_band(52), "52-53")
        self.assertEqual(diameter_band(53), "52-53")
        self.assertEqual(diameter_band(54), "54-55")
        self.assertEqual(diameter_band(56), "56+")
        self.assertEqual(diameter_band(63), "56+")
        self.assertEqual(diameter_band(48), "")
        self.assertEqual(diameter_band(None), "")

    def test_bare_diameter_next_to_a_durometer(self):
        parsed = wheel_specs("Spitfire Bighead Skateboard Wheels - white/red 63 (99d)")
        self.assertEqual(parsed["diameter_mm"], 63.0)
        self.assertEqual(parsed["durometers"], ["99d"])
        self.assertEqual(diameter_band(parsed["diameter_mm"]), "56+")

    def test_dual_durometers_and_ignored_classic(self):
        slash = wheel_specs("OJ Double Duro Chubbies 54mm 101a/95a White Skateboard Wheels")
        self.assertEqual(slash["durometers"], ["101a", "95a"])
        self.assertEqual(slash["diameter_mm"], 54.0)
        ampersand = wheel_specs("OJ Double Duro Chubbies 56mm 99a & 95a Skateboard Wheels")
        self.assertEqual(ampersand["durometers"], ["99a", "95a"])
        classic = wheel_specs("Spitfire Formula Four Classic Black & Orange 53mm 97a Skateboard Wheels")
        self.assertEqual(classic["shape"], "")
        self.assertEqual(classic["durometers"], ["97a"])
        self.assertEqual(wheel_specs("Bones 100's OG Formula V5 Sidecut Skateboard Wheels - white/blue (100a)")["durometers"], ["100a"])

    def test_shape_words_that_are_actually_shapes(self):
        self.assertEqual(
            wheel_specs("Spitfire Formula Four Conical Full 54mm 99a Wheels")["shape"],
            "conical",
        )
        self.assertEqual(
            wheel_specs("Spitfire Formula Four Radial Full 56mm 99a Green & Purple Swirl Skateboard Wheels")["shape"],
            "radial",
        )
        self.assertEqual(
            wheel_specs("Bones 100's OG Formula V5 Sidecut Skateboard Wheels - white/blue (100a)")["shape"],
            "sidecut",
        )
        self.assertEqual(
            wheel_specs("Bones Caballero SPF Side Cut Skateboard Wheels - bat wings (84b)")["shape"],
            "sidecut",
        )
        self.assertEqual(wheel_specs("Bones X-Formula side-cut 54mm 99a")["shape"], "sidecut")

    def test_two_diameters_are_not_guessed(self):
        parsed = wheel_specs("Mystery 52mm or 54mm 99a Wheels")
        self.assertIsNone(parsed["diameter_mm"])
        self.assertEqual(parsed["durometers"], ["99a"])


class TruckAndBearingSpecTests(unittest.TestCase):
    def test_hanger_ace_inch_and_axle_sizes(self):
        self.assertEqual(truck_specs("Independent Berle Skull 149 Stage 11 Silver & Orange Skateboard Truck")["size"], "149")
        self.assertEqual(truck_specs("Ace 60 AF1 Matte Black Skateboard Truck")["size"], "60")
        self.assertEqual(truck_specs("Ace AF-1 Hollow Skateboard Trucks - polished silver 66")["size"], "66")
        self.assertEqual(truck_specs("Slappy ST1 Ultra Low Inverted Hollow Lights 8.0\" Gunmetal Skateboard Truck")["size"], "8.0")
        self.assertEqual(truck_specs('Slappy x Heroin ST1 Wide Boys Hollow 11.0" Silver & Black Truck')["size"], "11.0")
        self.assertEqual(truck_specs("Venture Koston V8 Silver 5.6 Skateboard Truck")["size"], "5.6")

    def test_stage_percent_and_hollow_are_not_sizes_or_heights(self):
        stage = truck_specs("Independent Stage 11 Standard Bar Truck Flat Black")
        self.assertEqual(stage["size"], "")
        self.assertEqual(stage["height"], "")
        deal = truck_specs("SUPER DEAL -23%Independent S11 Frgd Titanium Joslin Sticker Slap Truck")
        self.assertEqual(deal["size"], "")
        hollow = truck_specs("Thunder Grenade Hollow Lights Grey 147 Skateboard Truck")
        self.assertEqual(hollow["size"], "147")
        self.assertEqual(hollow["height"], "")
        self.assertEqual(truck_specs("Independent Mid Truck Tiago Lemos")["height"], "mid")
        self.assertEqual(truck_specs("Ace 44 AF1 Low Hollow Silver Skateboard Truck")["height"], "low")
        self.assertEqual(truck_specs("Ace Classic Low Skateboard Trucks")["height"], "low")
        self.assertEqual(truck_specs("Some High Truck 149")["height"], "high")

    def test_two_hanger_sizes_stay_blank(self):
        self.assertEqual(truck_specs("Independent 139 or 149 Truck")["size"], "")
        self.assertEqual(truck_specs("Ace 55 and 66 AF1 Truck")["size"], "")

    def test_abec_ratings(self):
        self.assertEqual(bearing_specs("Bones Reds ABEC-7 Bearings")["abec"], "7")
        self.assertEqual(bearing_specs("ABEC 5 bearings")["abec"], "5")
        self.assertEqual(bearing_specs("ABEC7 skate bearings")["abec"], "7")
        self.assertEqual(bearing_specs("Bones Swiss Skateboard Bearings")["abec"], "")


class SpecQueryTests(unittest.TestCase):
    def test_spec_params_round_trip_and_defaults_stay_empty(self):
        self.assertEqual(encode_state({}), "")
        state = decode_query("type=wheel&diameter=56%2B%2C52-53&duro=101a,95a&shape=radial&trucksize=8.0,149&truckheight=low&abec=7")
        self.assertEqual(state["part"], "Wheels")
        self.assertEqual(state["diameters"], ["52-53", "56+"])
        self.assertEqual(state["duros"], ["95a", "101a"])
        self.assertEqual(state["shapes"], ["radial"])
        self.assertEqual(state["truck_sizes"], ["8.0", "149"])
        self.assertEqual(state["truck_heights"], ["low"])
        self.assertEqual(state["abecs"], ["7"])
        self.assertEqual(decode_query(encode_state(state)), state)
        ignored = decode_query("diameter=nope&duro=classic&shape=classic&trucksize=11&truckheight=hollow&abec=abec")
        self.assertEqual(ignored["diameters"], [])
        self.assertEqual(ignored["duros"], [])
        self.assertEqual(ignored["shapes"], [])
        self.assertEqual(ignored["truck_sizes"], [])
        self.assertEqual(ignored["truck_heights"], [])
        self.assertEqual(ignored["abecs"], [])
        self.assertEqual(encode_state(ignored), "")


class SpecSectionTests(unittest.TestCase):
    def test_sections_appear_only_past_a_handful(self):
        self.assertFalse(section_ready(MIN_SPEC_COUNT - 1))
        self.assertTrue(section_ready(MIN_SPEC_COUNT))
        wheels = [
            _item(f"OJ Elite {50 + index}mm 99a Skateboard Wheels", "Wheels", f"https://example.com/w{index}")
            for index in range(4)
        ]
        few = build_report_html({"Zumiez_Wheels": wheels}, {}, generated_at="2026-10-11T21:46:35+00:00")
        self.assertNotIn('data-section="diameter"', few)
        self.assertNotIn('data-section="duro"', few)
        self.assertNotIn('data-section="shape"', few)
        wheels.append(_item("Spitfire Formula Four Conical 56mm 101a/95a Skateboard Wheels", "Wheels", "https://example.com/w5"))
        enough = build_report_html({"Zumiez_Wheels": wheels}, {}, generated_at="2026-10-11T21:46:35+00:00")
        self.assertIn('data-section="diameter" data-for="Wheels"', enough)
        self.assertIn('data-section="duro" data-for="Wheels"', enough)
        self.assertNotIn('data-section="shape"', enough)
        self.assertIn('data-value="50-51"', enough)
        self.assertIn('data-value="52-53"', enough)
        self.assertIn('data-value="56+"', enough)
        self.assertIn('data-value="101a"', enough)
        self.assertIn('data-value="95a"', enough)
        self.assertIn("is-type-hidden", enough)
        row = next(part for part in enough.split("<tr ") if "example.com/w5" in part)
        self.assertIn('data-diameter="56+"', row)
        self.assertIn('data-duros="101a,95a"', row)
        self.assertIn('data-shape="conical"', row)
        self.assertIn('data-part="Wheels"', row)

    def test_truck_height_and_deck_length_follow_the_same_gate(self):
        trucks = [
            _item("Independent 149 Stage 11 Skateboard Truck", "Trucks", "https://example.com/t1"),
            _item("Independent 139 Stage 11 Skateboard Truck", "Trucks", "https://example.com/t2"),
            _item("Ace 55 Classic Skateboard Truck", "Trucks", "https://example.com/t3"),
            _item("Venture Silver 5.6 Skateboard Truck", "Trucks", "https://example.com/t4"),
            _item('Thunder Low 8.0" Skateboard Truck', "Trucks", "https://example.com/t5"),
        ]
        html = build_report_html({"Zumiez_Trucks": trucks}, {}, generated_at="2026-10-11T21:46:35+00:00")
        self.assertIn('data-section="trucksize" data-for="Trucks"', html)
        self.assertNotIn('data-section="truckheight"', html)
        self.assertIn('data-value="149"', html)
        self.assertIn('data-value="5.6"', html)
        self.assertIn('data-value="8.0"', html)
        self.assertIn("Hanger size 149 printed in the name", html)
        self.assertIn("Ace size 55 printed in the name", html)
        self.assertIn("Axle width 5.6 printed in the name", html)
        tall = trucks + [
            _item("Independent Mid 151 Skateboard Truck", "Trucks", "https://example.com/t6"),
            _item("Ace 44 Low Skateboard Truck", "Trucks", "https://example.com/t7"),
            _item("Thunder High 148 Skateboard Truck", "Trucks", "https://example.com/t8"),
            _item("Independent Mid 147 Skateboard Truck", "Trucks", "https://example.com/t9"),
            _item("Ace Low 33 Skateboard Truck", "Trucks", "https://example.com/t10"),
        ]
        tall_html = build_report_html({"Zumiez_Trucks": tall}, {}, generated_at="2026-10-11T21:46:35+00:00")
        self.assertIn('data-section="truckheight" data-for="Trucks"', tall_html)
        self.assertIn('data-value="low"', tall_html)
        self.assertIn('data-value="mid"', tall_html)
        self.assertIn('data-value="high"', tall_html)
        low = next(part for part in tall_html.split("<tr ") if "example.com/t5" in part)
        self.assertIn('data-trucksize="8.0"', low)
        self.assertIn('data-truckheight="low"', low)

        short = [
            _item(
                f"Powell Peralta Ripper {8 + index * 0.25:.2f} x 32 Skateboard Deck",
                "Decks",
                f"https://example.com/d{index}",
            )
            for index in range(4)
        ]
        short_html = build_report_html({"Zumiez_Decks": short}, {}, generated_at="2026-10-11T21:46:35+00:00")
        self.assertNotIn('data-section="length"', short_html)
        self.assertNotIn('data-section="wheelbase"', short_html)
        decks = short + [
            _item("Powell Peralta Ripper 9.0 x 32.25 Skateboard Deck", "Decks", "https://example.com/d5")
        ]
        deck_html = build_report_html({"Zumiez_Decks": decks}, {}, generated_at="2026-10-11T21:46:35+00:00")
        self.assertIn('data-section="length" data-for="Decks"', deck_html)
        self.assertIn('class="filter-section is-open is-type-hidden" data-section="width" data-for="Decks"', deck_html)
        self.assertNotIn('data-section="wheelbase"', deck_html)
        based = decks + [
            _item(
                f"Powell Peralta Ripper 8.{index} wheelbase 14.{index} Skateboard Deck",
                "Decks",
                f"https://example.com/wb{index}",
            )
            for index in range(5)
        ]
        wheelbase_html = build_report_html({"Zumiez_Decks": based}, {}, generated_at="2026-10-11T21:46:35+00:00")
        self.assertIn('data-section="wheelbase" data-for="Decks"', wheelbase_html)

    def test_live_catalog_coverage_gates(self):
        with open("previous_data.json", encoding="utf-8") as handle:
            data = json.load(handle)
        wheels = trucks = bearings = 0
        diameter = duro = shape = 0
        size = height = abec = 0
        length = wheelbase = decks = 0
        for key, items in data.items():
            part = str(key).rsplit("_", 1)[-1]
            for item in items or []:
                name = item.get("name") or ""
                if part == "Wheels":
                    wheels += 1
                    parsed = wheel_specs(name)
                    if diameter_band(parsed["diameter_mm"]):
                        diameter += 1
                    if parsed["durometers"]:
                        duro += 1
                    if parsed["shape"]:
                        shape += 1
                elif part == "Trucks":
                    trucks += 1
                    parsed = truck_specs(name)
                    if parsed["size"]:
                        size += 1
                    if parsed["height"]:
                        height += 1
                elif part == "Bearings":
                    bearings += 1
                    if bearing_specs(name)["abec"]:
                        abec += 1
                elif part == "Decks":
                    decks += 1
                    specs = extract_specs(name)
                    if specs.get("length"):
                        length += 1
                    if specs.get("wheelbase"):
                        wheelbase += 1
        self.assertGreaterEqual(diameter, MIN_SPEC_COUNT)
        self.assertGreaterEqual(duro, MIN_SPEC_COUNT)
        self.assertLess(shape, MIN_SPEC_COUNT)
        self.assertGreaterEqual(size, MIN_SPEC_COUNT)
        self.assertGreaterEqual(height, MIN_SPEC_COUNT)
        self.assertLess(abec, MIN_SPEC_COUNT)
        self.assertGreaterEqual(length, MIN_SPEC_COUNT)
        self.assertLess(wheelbase, MIN_SPEC_COUNT)
        self.assertGreater(wheels, 0)
        self.assertGreater(trucks, 0)
        self.assertEqual(bearings, 0)
        self.assertGreater(decks, 0)


if __name__ == "__main__":
    unittest.main()
