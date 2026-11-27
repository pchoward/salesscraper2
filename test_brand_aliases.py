"""One Brand filter entry per brand (owner, 2026-11-25: "Crank Bros" and
"Crankbrothers" were both in MTB's Brand filter)."""

import json
import unittest
from pathlib import Path

from sports.brands import _key, canonical

ROOT = Path(__file__).resolve().parent
ALIAS_FILES = [ROOT / "search" / "aliases.json"] + sorted((ROOT / "sports").glob("*/aliases.json"))


class BrandAliasTests(unittest.TestCase):
    def test_no_spelling_belongs_to_two_brands(self):
        # "OneUp" and "OneUp Components" were two entries, so stores' two
        # spellings stayed two brands.
        for path in ALIAS_FILES:
            brands = json.loads(path.read_text(encoding="utf-8")).get("brands") or {}
            owner = {}
            for name, others in brands.items():
                for spelling in [name, *(others or [])]:
                    key = _key(spelling)
                    if key in owner:
                        self.assertEqual(owner[key], name, f"{path.relative_to(ROOT)}: {spelling!r} is in "
                                                           f"{owner[key]!r} and {name!r}")
                    owner.setdefault(key, name)

    def test_store_spellings_found_in_the_feeds(self):
        mtb = ROOT / "sports" / "mtb" / "aliases.json"
        for spellings, brand in (
            (("Crank Bros", "Crank Brothers", "Crankbrothers", "CRANKBROTHERS"), "Crankbrothers"),
            (("OneUp", "OneUp Components", "One Up"), "OneUp Components"),
            (("Wolf Tooth", "Wolf Tooth Components"), "Wolf Tooth Components"),
            (("Onyx", "Onyx Racing Products"), "Onyx"),
            (("SunRace", "Sunrace"), "SunRace"),
            (("Kool Stop", "Kool-Stop"), "Kool-Stop"),
        ):
            for spelling in spellings:
                self.assertEqual(canonical(spelling, mtb), brand, spelling)
        ski = ROOT / "sports" / "ski" / "aliases.json"
        self.assertEqual(canonical("Treviso Design", ski), "Treviso")



class TradeWordTests(unittest.TestCase):
    """Owner, 2026-11-27: "Osprey" and "Osprey Packs" both in MTB's Brand list."""

    def merged(self, labels):
        import page
        records = [{"brand": label, "search": label, "item": {}} for label in labels]
        page._canonicalize_brands(records)
        return [record["brand"] for record in records]

    def test_a_trade_word_merges_into_the_bare_name(self):
        self.assertEqual(self.merged(["Osprey Packs", "Osprey", "Salomon Skis", "Salomon", "MTX Braking", "MTX"]),
                         ["Osprey", "Osprey", "Salomon", "Salomon", "MTX", "MTX"])

    def test_alone_it_keeps_its_name(self):
        # Nothing to merge with; different brands that share a first word stay apart.
        self.assertEqual(self.merged(["Osprey Packs", "Profile Design", "Profile", "Formula 100", "Formula"]),
                         ["Osprey Packs", "Profile Design", "Profile", "Formula 100", "Formula"])


if __name__ == "__main__":
    unittest.main()
