"""All-time-low flags in the report, and conservative cross-store matching."""

import unittest

from history import all_time_low_status
from matching import (
    brand_key,
    canonical_width,
    cross_store_groups,
    describe_item,
    explain_match,
    match_diagnostics,
    product_identity,
)
from report import Digest, build_report_html

TODAY = "2026-09-30"


def _deck(name, store, url, price="40.00", width_name=None):
    return {
        "name": name,
        "url": url,
        "price_new": price,
        "price_old": "90.00",
        "part": "Decks",
        "store": store,
    }


def _history_for(url, prices):
    days = sorted(prices)
    return {
        url: {
            "name": "tracked",
            "store": "Zumiez",
            "part": "Decks",
            "first_seen": days[0],
            "last_seen": days[-1],
            "observation_count": len(prices),
            "all_time_low": min(prices.values()),
            "all_time_low_date": min(day for day, price in prices.items() if price == min(prices.values())),
            "prices": prices,
        }
    }


class WidthAndIdentityTests(unittest.TestCase):
    def test_width_buckets_merge_rounding_but_not_real_size_steps(self):
        self.assertEqual(canonical_width(8.125), canonical_width(8.12))
        self.assertEqual(canonical_width(8.38), canonical_width(8.375))
        self.assertEqual(canonical_width(8.3875), canonical_width(8.38))
        self.assertNotEqual(canonical_width(8.475), canonical_width(8.5))
        self.assertNotEqual(canonical_width(8.0), canonical_width(8.06))
        self.assertNotEqual(canonical_width(8.25), canonical_width(8.28))

    def test_same_deck_matches_across_width_spellings(self):
        left = _deck(
            "Baker Figgy Divine Evil Deck 8.125",
            "Zumiez",
            "https://example.com/z",
            "64.99",
        )
        right = _deck(
            "Baker Figgy Divine Evil Deck 8.12 x 31.875",
            "SkateWarehouse",
            "https://example.com/s",
            "59.98",
        )
        self.assertEqual(product_identity(left)["key"], product_identity(right)["key"])
        groups = cross_store_groups([left, right])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["cheapest_price"], 59.98)
        stores = {offer["store"] for offer in groups[0]["offers"]}
        self.assertEqual(stores, {"Zumiez", "SkateWarehouse"})

    def test_different_width_or_model_does_not_match(self):
        base = _deck("Girl Howard Fullcourt Twin 8.25 Deck", "Zumiez", "https://example.com/a", "60.00")
        other_width = _deck(
            "Girl Howard Fullcourt Twin 8.0 Deck",
            "Tactics",
            "https://example.com/b",
            "50.00",
        )
        other_model = _deck(
            "Girl Howard Rick's Full Court 8.25 Deck",
            "CCS",
            "https://example.com/c",
            "55.00",
        )
        vague = _deck("Baker Team Deck 8.25", "Tactics", "https://example.com/d", "40.00")
        vague_two = _deck("Baker Team Deck 8.25", "CCS", "https://example.com/e", "41.00")
        self.assertNotEqual(product_identity(base)["key"], product_identity(other_width)["key"])
        self.assertNotEqual(product_identity(base)["key"], product_identity(other_model)["key"])
        self.assertIsNone(product_identity(vague))
        self.assertEqual(cross_store_groups([base, other_width, other_model, vague, vague_two]), [])

    def test_single_store_is_hidden_and_real_emb_can_match(self):
        only = _deck("Real EMB Deck 8.25", "Zumiez", "https://example.com/only", "50.00")
        self.assertEqual(cross_store_groups([only]), [])
        other = _deck("Real EMB Deck 8.25 x 32", "CCS", "https://example.com/ccs", "48.00")
        groups = cross_store_groups([only, other])
        self.assertEqual(len(groups), 1)
        self.assertIn("Real", groups[0]["label"])
        self.assertIn("EMB", groups[0]["label"])

    def test_wheels_need_diameter_and_trucks_keep_hollow_apart(self):
        conical = {
            "name": "Spitfire Formula Four Conical Full 54mm 99a Wheels",
            "url": "https://example.com/spit-z",
            "price_new": "35.00",
            "part": "Wheels",
            "store": "Zumiez",
        }
        conical_ccs = dict(conical, store="CCS", url="https://example.com/spit-c", price_new="32.00")
        radial = dict(
            conical,
            name="Spitfire Formula Four Radial Full 54mm 99a Wheels",
            store="Tactics",
            url="https://example.com/radial",
        )
        other_mm = dict(
            conical,
            name="Spitfire Formula Four Conical Full 56mm 99a Wheels",
            store="Tactics",
            url="https://example.com/56",
        )
        no_mm = dict(
            conical,
            name="Spitfire Formula Four Conical Full Wheels 99a",
            store="SkateWarehouse",
            url="https://example.com/nomm",
        )
        groups = cross_store_groups([conical, conical_ccs, radial, other_mm, no_mm])
        self.assertEqual(len(groups), 1)
        self.assertEqual({offer["store"] for offer in groups[0]["offers"]}, {"Zumiez", "CCS"})

        standard = {
            "name": "Independent Stage 11 Standard 149 Truck",
            "url": "https://example.com/indy-z",
            "price_new": "22.00",
            "part": "Trucks",
            "store": "Zumiez",
        }
        standard_ccs = dict(standard, store="CCS", url="https://example.com/indy-c", price_new="24.00")
        hollow = dict(
            standard,
            name="Independent Stage 11 Hollow 149 Truck",
            store="Tactics",
            url="https://example.com/hollow",
            price_new="20.00",
        )
        other_hanger = dict(
            standard,
            name="Independent Stage 11 Standard 139 Truck",
            store="SkateWarehouse",
            url="https://example.com/139",
        )
        truck_groups = cross_store_groups([standard, standard_ccs, hollow, other_hanger])
        self.assertEqual(len(truck_groups), 1)
        self.assertEqual({offer["store"] for offer in truck_groups[0]["offers"]}, {"Zumiez", "CCS"})

    def test_bones_swiss_matches_and_bones_reds_does_not(self):
        swiss = {
            "name": "Bones Swiss Skateboard Bearings",
            "url": "https://example.com/swiss-z",
            "price_new": "30.00",
            "price_old": "60.00",
            "part": "Bearings",
            "store": "Zumiez",
        }
        swiss_ccs = dict(swiss, store="CCS", url="https://example.com/swiss-c", price_new="28.00")
        reds = dict(
            swiss,
            name="Bones Reds Skateboard Bearings",
            store="Tactics",
            url="https://example.com/reds",
            price_new="18.00",
        )
        groups = cross_store_groups([swiss, swiss_ccs, reds])
        self.assertEqual(len(groups), 1)
        self.assertEqual({offer["store"] for offer in groups[0]["offers"]}, {"Zumiez", "CCS"})


def _item(part, name, store, price="40.00", url=None):
    return {
        "name": name,
        "url": url or f"https://example.com/{store}/{abs(hash(name))}",
        "price_new": price,
        "price_old": "90.00",
        "part": part,
        "store": store,
    }


def _key(part, name):
    identity = product_identity(_item(part, name, "Zumiez"))
    return identity["key"] if identity else None


class CrossRetailerNamingTests(unittest.TestCase):
    """The same product written the way each store writes it. Names are from the catalog."""

    def assertSame(self, part, *names):
        keys = {_key(part, name) for name in names}
        self.assertNotIn(None, keys, names)
        self.assertEqual(len(keys), 1, names)

    def test_deck_width_inch_mark_and_width_by_length(self):
        self.assertSame(
            "Decks",
            'Baker Baca Cerberus 8.5" Skateboard Deck',
            "Baker Baca Cerberus 8.5 Skateboard Deck",
            "Baker Baca Cerberus Deck 8.5 x 31.875",
            "Baker Baca Cerberus Deck 8.50x32",
        )

    def test_deck_collab_x_case_and_rounded_widths(self):
        self.assertSame(
            "Decks",
            'There x Sneakdiss Battle Ship 8.5" Skateboard Deck',
            "There Sneakdiss Battle Ship Deck 8.5 x 31.85",
        )
        self.assertSame(
            "Decks",
            'enjoi Big Box Plastic Spectrum 8.25" Skateboard Deck',
            "Enjoi Big Box Plastic Spectrum Deck 8.25 x 32",
        )
        self.assertSame(
            "Decks",
            'Real Nicole Pig Run 8.38" Skateboard Deck',
            "Real Nicole Pig Run Deck 8.375 x 32.25",
        )
        self.assertSame(
            "Decks",
            'WKND Thompson Interstate 8.0" Skateboard Deck',
            "WKND Thompson Interstate 8 x 31.5 Deck",
        )

    def test_deck_edition_number_spellings(self):
        self.assertSame(
            "Decks",
            'EDGLRD Barrio Triste 003 8.38" Skateboard Deck',
            "EDGLRD Barrio Triste #003 Deck 8.38 x 32.1",
        )

    def test_deck_brand_spellings_fold(self):
        self.assertSame(
            "Decks",
            "Deathwish Jake Hayes Shinobi Deck 8.25 x 31.676",
            'Death Wish Jake Hayes Shinobi 8.25" Skateboard Deck',
        )
        self.assertSame(
            "Decks",
            "Anti Hero Doobie Expressions Deck 8.75 x 31.75",
            'Anti-Hero Doobie Expressions 8.75" Skateboard Deck',
        )
        # "Jacuzzi Unlimited" is the full company name; Zumiez writes "Jacuzzi".
        self.assertSame(
            "Decks",
            "Jacuzzi Unlimited Mitchell Race Car Deck 8.5 x 32.2",
            'Jacuzzi Mitchell Race Car 8.5" Skateboard Deck',
        )
        self.assertEqual(brand_key("Indy"), brand_key("Independent"))
        self.assertEqual(brand_key("Death Wish"), brand_key("Deathwish"))

    def test_deck_apostrophes_and_ampersands(self):
        self.assertSame(
            "Decks",
            "April Shane O'Neill Dead Black Dip Deck 8.25x31.92",
            "April Shane O\u2019Neill Dead Black Dip 8.25 Skateboard Deck",
        )
        self.assertSame(
            "Decks",
            'Foundation Star & Moon 8.38" Skateboard Deck',
            "Foundation Star And Moon 8.375 Skateboard Deck",
        )

    def test_wheel_spacing_case_and_word_order(self):
        self.assertSame(
            "Wheels",
            "Spitfire Formula Four Conical Full 54mm 99a Skateboard Wheels",
            "Spitfire Formula Four Conical Full 99A 54 mm Wheels",
            "Spitfire Formula Four 54mm 99a Conical Full Wheels",
        )

    def test_wheel_decimal_diameter_and_double_durometer(self):
        self.assertSame(
            "Wheels",
            "Spitfire Diego Rude Awakening Formula Four 55.5mm 99a White Skateboard Wheels",
            "Spitfire Diego Rude Awakening Formula Four 55.50mm 99a White Wheels",
        )
        self.assertSame(
            "Wheels",
            "OJ Double Duro Chubbies 54mm 101a/95a White Skateboard Wheels",
            "OJ Double Duro Chubbies 54mm 95A/101A White Wheels",
        )

    def test_powell_peralta_spellings(self):
        self.assertSame(
            "Wheels",
            "Powell-Peralta Dragon Formula 54mm 93a Skateboard Wheels",
            "Powell Peralta Dragon Formula 54mm 93a Wheels",
            "Powell Dragon Formula 54mm 93a Wheels",
        )

    def test_truck_stage_brand_and_abbreviation_spellings(self):
        self.assertSame(
            "Trucks",
            "Independent Stage 11 Hollow 149 Skateboard Truck",
            "Indy S11 Hollow 149 Truck",
            "Independent 149 Stage 11 Hollow Truck",
        )
        self.assertSame(
            "Trucks",
            "Independent S11 Frgd Titanium 144 Truck Blk",
            "Independent Stage 11 Forged Titanium 144 Black Truck",
        )

    def test_truck_hanger_position_and_ace_sizes(self):
        self.assertSame(
            "Trucks",
            "Ace AF-1 Skateboard Trucks - polished silver 60",
            "Ace 60 AF1 Polished Silver Skateboard Truck",
        )
        self.assertSame(
            "Trucks",
            "Slappy ST1 Hollow Skateboard Trucks - polished 8.0",
            "Slappy ST1 Hollow 8.00 Polished Truck",
        )

    def test_bearing_case_and_accents(self):
        self.assertSame("Bearings", "Bones Super Reds Bearings", "Bones Super REDS Skateboard Bearings")
        self.assertSame("Bearings", "Andalé Blue Pearl Bearings", "Andale Blue Pearl Skateboard Bearings")

    def test_groups_across_three_stores_pick_cheapest(self):
        items = [
            _item("Decks", "Chocolate Anderson Jazz Lovers 8.5\" Skateboard Deck", "Zumiez", "54.95"),
            _item("Decks", "Chocolate Anderson Jazz Lovers Deck 8.5x31.625", "SkateWarehouse", "49.95"),
            _item("Decks", "Chocolate Anderson Jazz Lovers 8.5 Skateboard Deck", "Tactics", "52.00"),
        ]
        groups = cross_store_groups(items)
        self.assertEqual(len(groups), 1)
        self.assertEqual([offer["store"] for offer in groups[0]["offers"]], ["Zumiez", "SkateWarehouse", "Tactics"])
        self.assertEqual(groups[0]["cheapest_price"], 49.95)


class MustNotMatchTests(unittest.TestCase):
    def assertApart(self, part, left, right):
        a, b = _key(part, left), _key(part, right)
        if a is not None and b is not None:
            self.assertNotEqual(a, b, (left, right))
        self.assertFalse(explain_match(_item(part, left, "Zumiez"), _item(part, right, "CCS"))["match"])

    def test_deck_widths(self):
        self.assertApart("Decks", "Chocolate Anderson Jazz Lovers Deck 8.5x31.625", "Chocolate Anderson Jazz Lovers 8.25 Skateboard Deck")
        self.assertApart("Decks", 'EDGLRD Barrio Triste 001 8.25" Skateboard Deck', "EDGLRD Barrio Triste #001 Deck 8.18 x 31.77")
        self.assertApart("Decks", 'Baker Baca Cerberus 8.0" Deck', 'Baker Baca Cerberus 8.06" Deck')
        self.assertApart("Decks", 'Baker Baca Cerberus 8.475" Deck', 'Baker Baca Cerberus 8.5" Deck')
        self.assertApart("Decks", 'Creature Logo Spray 9.0 Deck', 'Creature Logo Spray 9.3 Deck')

    def test_deck_model_variants(self):
        # Edition numbers are model words, not noise.
        self.assertApart("Decks", 'EDGLRD Barrio Triste 003 8.5" Deck', 'EDGLRD Barrio Triste 004 8.5" Deck')
        self.assertApart("Decks", "Creature Web 2 Relic Deck 8.5 x 31.88", 'Creature Web Relic 8.5" Deck')
        self.assertApart("Decks", 'Powell Ripper OG 16 8.25" Deck', 'Powell Ripper OG 17 8.25" Deck')
        # R7 is a construction, Twin and ATV are shapes or lines.
        self.assertApart("Decks", "Madness Repeat Offender R7 Deck 8.25 x 32", 'Madness Repeat Offender 8.25" Skateboard Deck')
        self.assertApart("Decks", 'Girl Howard Fullcourt Twin 8.25 Deck', 'Girl Howard Fullcourt 8.25 Deck')
        self.assertApart("Decks", "Creature Logo Spray Deck 9.0 x 32.0", "Creature Logo Spray ATV 9.0 Skateboard Deck")
        self.assertApart("Decks", "Lovesick Strubing Last Kiss Deck 8.375 x 32", "Lovesick Strubing Last Kiss 8.375 Skateboard Deck - blue")

    def test_wheel_diameters(self):
        self.assertApart("Wheels", "Spitfire Formula Four Classic 53mm 99a Wheels", "Spitfire Formula Four Classic 54mm 99a Wheels")
        self.assertApart("Wheels", "Spitfire Diego Rude Awakening Formula Four 55.5mm 99a Wheels", "Spitfire Diego Rude Awakening Formula Four 55mm 99a Wheels")

    def test_wheel_durometers(self):
        self.assertApart("Wheels", "Spitfire Formula Four Conical Full 54mm 99a Wheels", "Spitfire Formula Four Conical Full 54mm 101a Wheels")
        self.assertApart("Wheels", "OJ Double Duro Hardline 54mm 101a/95a Wheels", "OJ Double Duro Hardline 54mm 99a/95a Wheels")
        self.assertApart("Wheels", "Bones SPF Scorpeedo 56mm 81B Sidecut Wheels", "Bones SPF Scorpeedo 56mm 84B Sidecut Wheels")

    def test_wheel_shapes_and_editions(self):
        self.assertApart("Wheels", "Spitfire Formula Four Conical Full 54mm 99a Wheels", "Spitfire Formula Four Conical 54mm 99a Wheels")
        self.assertApart("Wheels", "Spitfire Formula Four Conical Full 54mm 99a Wheels", "Spitfire Formula Four Radial Full 54mm 99a Wheels")
        self.assertApart("Wheels", "Bones X-Formula V5 Sidecut 53mm 99a Wheels", "Bones X-Formula V6 Wide-Cut 53mm 99a Wheels")
        self.assertApart("Wheels", "OJ Sanbongi 2 Original Mini Combo 54mm 99a Wheels", "OJ Sanbongi Original Mini Combo 54mm 99a Wheels")

    def test_truck_sizes(self):
        self.assertApart("Trucks", "Independent Stage 11 Hollow 149 Truck", "Independent Stage 11 Hollow 144 Truck")
        self.assertApart("Trucks", "Slappy ST1 Hollow 8.0 Truck", "Slappy ST1 Hollow 8.25 Truck")
        self.assertApart("Trucks", "Ace 55 AF1 Polished Truck", "Ace 60 AF1 Polished Truck")

    def test_truck_constructions_heights_and_models(self):
        self.assertApart("Trucks", "Independent Stage 11 Hollow 149 Truck", "Independent Stage 11 Standard 149 Truck")
        self.assertApart("Trucks", "Independent Stage 11 Forged Titanium 149 Truck", "Independent Stage 11 Forged Hollow 149 Truck")
        self.assertApart("Trucks", "Independent Stage 11 Hollow 149 Truck", "Independent Stage 4 Hollow 149 Truck")
        self.assertApart("Trucks", "Venture V-Hollow 5.6 Hi Truck", "Venture V-Hollow 5.6 Low Truck")
        self.assertApart("Trucks", "Independent Stage 11 Inverted Kingpin 149 Truck", "Independent Stage 11 Standard 149 Truck")
        self.assertApart("Trucks", "Ace 33 AF1 Polished Truck", "Ace 33 Classic Polished Truck")
        self.assertApart("Trucks", "Slappy ST1 Inverted Hollow Lights 8.75 Truck", "Slappy Hollow 8.75 Polished Truck")
        # A single truck is half the price of a pair.
        self.assertApart("Trucks", "SINGLE Independent Stage 11 Hollow 149 Truck", "Independent Stage 11 Hollow 149 Truck")

    def test_bearing_models(self):
        self.assertApart("Bearings", "Bones Reds Bearings", "Bones Super Reds Bearings")
        self.assertApart("Bearings", "Bronson G2 Bearings", "Bronson G3 Bearings")
        self.assertApart("Bearings", "Bones Swiss Bearings", "Bones Swiss Ceramic Bearings")
        self.assertApart("Bearings", "Bones Swiss 6 Ball Bearings", "Bones Swiss Bearings")
        self.assertApart("Bearings", "Bronson G3 Bearings", "Bronson x Black Sabbath G3 Bearings - Black")

    def test_different_parts_and_brands(self):
        deck = _item("Decks", 'Powell Dragon 8.25" Deck', "Zumiez")
        wheel = _item("Wheels", "Powell Dragon Formula 54mm 93a Wheels", "CCS")
        self.assertFalse(explain_match(deck, wheel)["match"])
        self.assertApart("Wheels", "Bones STF V5 Sidecut 54mm 99a Wheels", "Spitfire STF V5 Sidecut 54mm 99a Wheels")


class IncompleteInformationTests(unittest.TestCase):
    """A missing or ambiguous attribute is never filled in by guessing."""

    def assertNoIdentity(self, part, name, problem):
        info = describe_item(_item(part, name, "Zumiez"))
        self.assertIsNone(info["key"], name)
        self.assertTrue(any(problem in text for text in info["problems"]), info["problems"])

    def test_missing_or_ambiguous_sizes(self):
        self.assertNoIdentity("Decks", "Welcome x Harry Potter Voldemort On A Dark Lord Skateboard Deck", "no deck width")
        self.assertNoIdentity("Wheels", "Bones X-Formula V5 Sidecut Skateboard Wheels - white/gold (99a)", "no wheel diameter")
        self.assertNoIdentity("Wheels", "Spitfire Formula Four Conical Full 52mm/54mm 99a Wheels", "more than one wheel diameter")
        self.assertNoIdentity("Trucks", "Independent Stage 11 Hollow Andrew Allen Truck", "no truck hanger")
        self.assertNoIdentity("Trucks", "Independent Stage 11 Hollow 139/144 Truck", "more than one truck size")
        self.assertNoIdentity("Trucks", "Slappy ST1 Hollow 8.0 / 8.25 Truck", "more than one truck size")

    def test_wheels_without_durometer_are_never_grouped(self):
        # Formula Four Conical Full comes in 99a and 101a at 54mm; without a
        # durometer the two listings could be different wheels.
        left = _item("Wheels", "Spitfire Formula Four Conical Full 54mm Wheels", "Zumiez", "35.00")
        right = _item("Wheels", "Spitfire Formula Four Conical Full 54mm Wheels", "CCS", "32.00")
        self.assertNoIdentity("Wheels", left["name"], "no durometer")
        self.assertEqual(cross_store_groups([left, right]), [])
        with_duro = dict(right, name="Spitfire Formula Four Conical Full 54mm 99a Wheels")
        self.assertEqual(cross_store_groups([left, with_duro]), [])
        explained = explain_match(left, with_duro)
        self.assertFalse(explained["match"])
        self.assertIn(
            {"attribute": "durometer", "left": None, "right": "99a"},
            explained["incomplete"],
        )

    def test_one_side_missing_width_does_not_match(self):
        sized = _item("Decks", 'Welcome Nora Fairy Tale 8.5" Deck', "Zumiez")
        unsized = _item("Decks", "Welcome Nora Fairy Tale Skateboard Deck", "CCS")
        self.assertEqual(cross_store_groups([sized, unsized]), [])
        self.assertIn({"attribute": "width", "left": '8.5"', "right": None}, explain_match(sized, unsized)["incomplete"])

    def test_unknown_brands_and_generic_names(self):
        self.assertNoIdentity("Wheels", "Ricta Clouds 54mm 92a Wheels", "brand not recognized")
        self.assertNoIdentity("Wheels", "Spitfire Formula Four 54mm 99a Wheels", "too generic")
        self.assertNoIdentity("Decks", "Baker Team Deck 8.25", "too generic")
        self.assertNoIdentity("Decks", 'Baker 003 8.25" Deck', "too generic")
        self.assertNoIdentity("Trucks", "Ace 33 Classic Silver Skateboard Truck", "too generic")
        self.assertNoIdentity("Bearings", "Bones Bearings", "too generic")

    def test_bad_input_does_not_raise(self):
        for item in (None, "text", {}, {"part": "Decks"}, {"part": "Sneakers", "name": "Nike SB"}):
            self.assertIsNone(product_identity(item))
        self.assertEqual(cross_store_groups([None, {}, {"part": "Decks", "name": 'Baker 8"'}]), [])


class MatchExplanationTests(unittest.TestCase):
    def test_explains_a_match(self):
        left = _item("Decks", "Baker Figgy Divine Evil Deck 8.125", "Zumiez")
        right = _item("Decks", "Baker Figgy Divine Evil Deck 8.12 x 31.875", "SkateWarehouse")
        result = explain_match(left, right)
        self.assertTrue(result["match"])
        self.assertEqual(
            [entry["attribute"] for entry in result["matched"]],
            ["part", "brand", "width", "model words"],
        )
        self.assertEqual(result["blocked"], [])
        self.assertEqual(result["incomplete"], [])
        self.assertEqual(result["summary"], "Match on part, brand, width, model words")

    def test_explains_what_blocked_a_match(self):
        left = _item("Wheels", "Spitfire Formula Four Conical Full 54mm 99a Wheels", "Zumiez")
        right = _item("Wheels", "Spitfire Formula Four Conical Full 54mm 101a Wheels", "CCS")
        result = explain_match(left, right)
        self.assertFalse(result["match"])
        self.assertEqual(result["blocked"], [{"attribute": "durometer", "left": "99a", "right": "101a"}])
        self.assertIn({"attribute": "diameter", "value": "54mm"}, result["matched"])
        self.assertEqual(result["summary"], "No match: different durometer")

        twin = explain_match(
            _item("Decks", "Girl Howard Fullcourt Twin 8.25 Deck", "Zumiez"),
            _item("Decks", "Girl Howard Fullcourt 8.25 Deck", "CCS"),
        )
        self.assertEqual(twin["blocked"], [{"attribute": "model words", "left": "twin", "right": "(none extra)"}])

    def test_explanation_agrees_with_identity_for_every_pair(self):
        names = [
            ("Decks", "Baker Baca Cerberus 8.5 Skateboard Deck"),
            ("Decks", "Baker Baca Cerberus Deck 8.5 x 31.875"),
            ("Decks", "Baker Baca Cerberus 8.25 Skateboard Deck"),
            ("Decks", "Baker Team Deck 8.25"),
            ("Decks", "Jacuzzi Unlimited Pilz Storybook Deck 9.0 x 32.1"),
            ("Decks", 'Jacuzzi Pilz Storybook 9.0" Skateboard Deck'),
            ("Wheels", "Spitfire Formula Four Conical Full 54mm 99a Wheels"),
            ("Wheels", "Spitfire Formula Four Conical Full 54mm Wheels"),
            ("Wheels", "Spitfire Formula Four Conical Full 99A 54 mm Wheels"),
            ("Trucks", "Indy S11 Hollow 149 Truck"),
            ("Trucks", "Independent Stage 11 Hollow 149 Skateboard Truck"),
            ("Trucks", "Independent Stage 11 Hollow Truck"),
            ("Bearings", "Bones Swiss Bearings"),
            ("Bearings", "Bones Swiss Skateboard Bearings"),
        ]
        items = [_item(part, name, "Zumiez") for part, name in names]
        for i, left in enumerate(items):
            for right in items[i:]:
                a, b = product_identity(left), product_identity(right)
                same = a is not None and b is not None and a["key"] == b["key"]
                result = explain_match(left, right)
                self.assertEqual(result["match"], same, (left["name"], right["name"]))
                if not same:
                    self.assertTrue(result["blocked"] or result["incomplete"], (left["name"], right["name"]))

    def test_groups_carry_an_explanation_only_when_asked(self):
        items = [
            _item("Trucks", "Independent Stage 11 Hollow 149 Skateboard Truck", "Zumiez", "60.00"),
            _item("Trucks", "Indy S11 Hollow 149 Truck", "SkateWarehouse", "55.00"),
        ]
        plain = cross_store_groups(items)
        self.assertEqual(len(plain), 1)
        self.assertNotIn("explanation", plain[0])
        explained = cross_store_groups(items, explain=True)
        self.assertEqual(
            explained[0]["explanation"],
            {
                "part": "Trucks",
                "brand": "Independent",
                "sizes": {"truck size": "149"},
                "model_words": ["stage11", "Hollow"],
            },
        )
        without = [dict(group) for group in explained]
        for group in without:
            group.pop("explanation")
        self.assertEqual(without, plain)


class DeterminismAndDiagnosticsTests(unittest.TestCase):
    def _catalog(self):
        return [
            _item("Decks", 'enjoi Big Box Plastic Spectrum 8.25" Skateboard Deck', "Zumiez", "59.95", "https://z/1"),
            _item("Decks", "Enjoi Big Box Plastic Spectrum Deck 8.25 x 32", "SkateWarehouse", "49.95", "https://s/1"),
            _item("Decks", "Enjoi Big Box Plastic Spectrum Deck 8.25 x 32", "SkateWarehouse", "49.95", "https://s/0"),
            _item("Decks", "Chocolate Anderson Jazz Lovers Deck 8.5x31.625", "SkateWarehouse", "49.95", "https://s/2"),
            _item("Decks", "Chocolate Anderson Jazz Lovers 8.25 Skateboard Deck", "Tactics", "45.00", "https://t/2"),
            _item("Wheels", "Spitfire Formula Four Conical Full 54mm Wheels", "CCS", "30.00", "https://c/3"),
            _item("Wheels", "Bones X-Formula V5 Sidecut Skateboard Wheels - white/gold (99a)", "Tactics", "30.00", "https://t/4"),
        ]

    def test_input_order_does_not_change_groups(self):
        items = self._catalog()
        forward = cross_store_groups(items, explain=True)
        backward = cross_store_groups(list(reversed(items)), explain=True)
        self.assertEqual(forward, backward)
        self.assertEqual(len(forward), 1)
        # Same store, same price: the earlier URL wins every time.
        self.assertIn("https://s/0", [offer["url"] for offer in forward[0]["offers"]])
        self.assertEqual(forward[0]["label"], 'Enjoi Big Box Plastic Spectrum 8.25"')

    def test_diagnostics_report_near_misses_and_unmatchable_items(self):
        report = match_diagnostics(self._catalog())
        self.assertEqual(report, match_diagnostics(list(reversed(self._catalog()))))
        self.assertEqual(len(report["groups"]), 1)
        self.assertEqual(report["near_miss_count"], 1)
        near = report["near_misses"][0]
        self.assertEqual(near["blocked"], {"attribute": "width", "left": '8.5"', "right": '8.25"'})
        self.assertEqual(
            report["unmatchable"]["Wheels"],
            {"no durometer in the name": 1, "no wheel diameter": 1},
        )


class ReportSectionTests(unittest.TestCase):
    def test_report_highlights_cheapest_and_flags_all_time_low(self):
        cheap = _deck(
            "Baker Figgy Divine Evil Deck 8.25",
            "SkateWarehouse",
            "https://example.com/cheap",
            "50.00",
        )
        pricey = _deck(
            "Baker Figgy Divine Evil Deck 8.25",
            "Zumiez",
            "https://example.com/pricey",
            "64.99",
        )
        fresh = _deck("Baker Brand New 8.0 Deck", "CCS", "https://example.com/fresh", "40.00")
        lone = _deck("Real EMB Deck 8.5", "Tactics", "https://example.com/lone", "48.00")
        data = {
            "SkateWarehouse_Decks": [cheap],
            "Zumiez_Decks": [pricey],
            "CCS_Decks": [fresh],
            "Tactics_Decks": [lone],
        }
        history = {}
        history.update(
            _history_for(
                cheap["url"],
                {"2026-09-01": 60.0, "2026-09-15": 55.0, "2026-09-30": 50.0},
            )
        )
        history.update(_history_for(fresh["url"], {"2026-09-30": 40.0}))
        warning = {
            "store": "Zumiez",
            "part": "Decks",
            "kind": "empty",
            "dates": ["2026-09-29", "2026-09-30"],
            "last_positive_date": "2026-09-28",
            "last_positive_count": 12,
        }
        digest = Digest(warnings=[warning])
        html = build_report_html(
            data,
            {},
            history,
            generated_at="2026-09-30 08:00:00",
            digest=digest,
        )
        self.assertNotIn('id="storeAlerts"', html)
        self.assertNotIn("Store check failed", html)
        self.assertNotIn('id="diagnostics"', html)
        self.assertNotIn('id="diagToggle"', html)
        self.assertNotIn("came back with no items two runs in a row", html)
        self.assertNotIn("Last good run on 2026-09-28 had 12 items", html)
        self.assertIn('id="compareSection"', html)
        self.assertIn('class="offer cheapest"', html)
        self.assertIn('data-store="SkateWarehouse"', html)
        compare = html.split('id="compareSection"', 1)[1].split('id="retailerActivity"', 1)[0]
        self.assertIn("$50.00", compare)
        self.assertIn("$64.99", compare)
        self.assertNotIn("Real EMB", compare)
        self.assertNotIn("Brand New", compare)
        self.assertEqual(compare.count('class="offer cheapest"'), 1)
        self.assertIn("ALL-TIME LOW", html)
        self.assertIn('id="atlSection"', html)
        atl = html.split('id="atlSection"', 1)[1].split('id="goneSection"', 1)[0]
        self.assertIn("Baker Figgy Divine Evil", atl)
        self.assertNotIn("Brand New", atl)
        self.assertTrue(all_time_low_status(cheap, history)["flagged"])
        self.assertFalse(all_time_low_status(fresh, history)["flagged"])


if __name__ == "__main__":
    unittest.main()
