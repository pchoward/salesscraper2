"""SkatePro (owner, 2026-11-03): skate, BMX and snow protection from its
category pages; only cards with a normal price above the selling price.
No network."""

import unittest

import sports
from sports.rules import bmx as bmx_rule
from stores import skatepro


def card(href, brand, name, price, listed=None):
    old = (f'<span class="visually_hidden">Normal price </span> <span class="product_card__list_price">${listed}</span>'
           if listed else "")
    sale = " product_card__selling_price--sale" if listed else ""
    return (f'<div role="listitem"><a class="product_card" href="https://www.skatepro.com/en-us/{href}.htm?stockcode=X">'
            f'<div class="product_card__image"><img src="https://cdn.skatepro.com/p/{href}.webp" alt=""></div>'
            f'<div class="product_card__brand">{brand}</div><h2 class="product_card__name">{name}</h2>'
            f'<div class="product_card__price"><span class="product_card__selling_price{sale}">'
            f'<span class="product_card__price_value">${price}</span></span> {old}</div></a></div>')


PAGE = "".join([
    card("482-1", "Triple Eight", "Gotham Dual Certified Helmet", "39.95", "64.95"),
    card("482-2", "Shadow", "Featherweight Helmet", "54.95"),                         # not on sale
    card("498-3", "Triple Eight", "KP 22 Knee Pads", "19.95", "34.95"),
    card("482-4", "Pro-Tec", "Classic Snow Helmet", "49.95", "89.95"),               # snow: not BMX
])


class SkateProTests(unittest.TestCase):
    def test_cards(self):
        found = skatepro.cards(PAGE)
        self.assertEqual(len(found), 4)
        self.assertEqual(found[0]["url"], "https://www.skatepro.com/en-us/482-1.htm", "no stockcode in the URL")
        self.assertEqual((found[0]["price"], found[0]["list_price"]), (39.95, 64.95))
        self.assertIsNone(found[1]["list_price"])

    def test_bmx_deals_with_filters(self):
        with sports.BMX.active():
            items = skatepro.SkateProScraper("bmx", "Protection", skatepro.bmx_extra).parse(PAGE)
        self.assertEqual({i["name"]: i["technical_specs"]["protects"] for i in items},
                         {"Triple Eight Gotham Dual Certified Helmet": ["Helmets"], "Triple Eight KP 22 Knee Pads": ["Knees"]})
        self.assertEqual({i["brand"] for i in items}, {"Triple 8"})

    def test_pages_until_nothing_new(self):
        pages = {1: PAGE, 2: card("482-9", "S-One", "Lifer Helmet", "39.95", "59.95"), 3: PAGE}
        requested = []

        def fetch(url):
            requested.append(url)
            number = int(url.split("page=")[1]) if "page=" in url else 1
            return pages.get(number, "")

        found = skatepro.load(482, fetch=fetch, sleep=lambda seconds: None)
        self.assertEqual(len(found), 5)
        self.assertEqual(len(requested), 3, "page 3 repeats page 1, so it stops")

    def test_each_sport_has_its_categories(self):
        self.assertEqual(set(skatepro.CATEGORIES), {"skate", "bmx", "ski"})
        self.assertEqual(set(skatepro.CATEGORIES["ski"]), {"Helmets", "Protection"})


class BmxTidyTests(unittest.TestCase):
    def test_protection_must_say_what_it_protects(self):
        self.assertEqual(bmx_rule("Shadow Featherweight Helmet Replacement Pads", "Protection", product_type="Helmets"),
                         "not protective gear")
        self.assertIsNone(bmx_rule("Fly Racing Lite Gloves", "Protection"))
        self.assertIsNone(bmx_rule("Kali Maya 3.0 Helmet", "Protection"))


if __name__ == "__main__":
    unittest.main()
