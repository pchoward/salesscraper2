"""Pack features like Tactics' sidebar (owner, 2026-11-27): skateboard
straps, water resistant, hydration compatible, waist and chest straps."""

import datetime
import unittest

from sports import packs
from stores import details

TODAY = datetime.date(2026, 11, 27)


class FeatureTests(unittest.TestCase):
    def test_from_the_description(self):
        self.assertEqual(packs.features("Vans Obstacle Skatepack",
                                        "Carries your skateboard with vertical skate straps. Water-resistant base."),
                         ["Skateboard straps", "Water resistant"])
        self.assertEqual(packs.features("Osprey Raptor 14", "Includes a 2.5L reservoir, sternum strap and hip belt."),
                         ["Hydration compatible", "Waist strap", "Chest strap"])
        self.assertEqual(packs.features("Element Mohave Backpack", "Board carry straps on the front. DWR finish."),
                         ["Skateboard straps", "Water resistant"])

    def test_snow_board_carry_is_not_a_skateboard_strap(self):
        self.assertEqual(packs.features("Dakine Heli Pro 20L", "Diagonal ski and board carry straps for snowboards."), [])

    def test_a_hydration_pack_is_hydration_compatible(self):
        self.assertEqual(packs.features("CamelBak M.U.L.E. Hydration Pack", ""), ["Hydration compatible"])

    def test_nothing_stated_means_none(self):
        self.assertEqual(packs.features("Herschel Little America Backpack", "Magnetic strap closures."), [])

    def test_offers_and_fields(self):
        item = {"name": "Vans Obstacle Skatepack", "price_new": "40", "price_old": "60",
                "pack_features": ["Skateboard straps"]}
        self.assertEqual(packs.technical_offers(item)[0]["specs"]["pack_features"], ["Skateboard straps"])
        self.assertNotIn("pack_features", packs.technical_offers({"name": "Herschel Pop Quiz", "price_new": "40"})[0]["specs"])
        field = packs.facet_fields("ski")[2]
        self.assertEqual((field["key"], field["param"], field["order"]),
                         ("pack_features", "ski_packfeat", list(packs.PACK_FEATURES)))


class ShopifyTests(unittest.TestCase):
    def test_feed_description_gives_features(self):
        from sports.ski import stores
        from stores import shopify
        product = {"handle": "dakine-mission", "title": "Dakine Mission 25L Backpack", "vendor": "Dakine",
                   "product_type": "Backpacks", "tags": ["water-resistant"],
                   "body_html": "<p>Padded <b>sternum strap</b> and DWR coating.</p>",
                   "variants": [{"id": 1, "title": "Black", "price": "60.00", "compare_at_price": "90.00", "available": True}]}
        items = shopify.ShopifyScraper(stores.EVO, "Packs").products_from([product])
        self.assertEqual(items[0]["pack_features"], ["Water resistant", "Chest strap"])


class ProductPageTests(unittest.TestCase):
    def data(self):
        return {"Tactics_Packs": [{"name": "Vans Obstacle Skatepack", "url": "https://www.tactics.com/vans/obstacle",
                                   "part": "Packs", "store": "Tactics"}],
                "Zumiez_Packs": [{"name": "Element Mohave Backpack", "url": "https://www.zumiez.com/element-mohave.html",
                                  "part": "Packs", "store": "Zumiez"}],
                "Tactics_Decks": [{"name": "Baker Deck", "url": "https://www.tactics.com/baker/deck", "part": "Decks",
                                   "store": "Tactics"}]}

    def history(self):
        return {"https://www.tactics.com/vans/obstacle": {}, "https://www.zumiez.com/element-mohave.html": {},
                "https://www.tactics.com/baker/deck": {}}

    def test_reads_each_pack_once(self):
        data, history = self.data(), self.history()
        static = ('<html><nav>Water Resistant packs</nav><div class="product-description">Skate straps carry '
                  'your board.</div></html>')
        rendered = ('<script type="application/ld+json">{"@type": "Product", "description": '
                    '"<p>Chest strap. Waterproof base.</p>"}</script>')
        calls = []
        read = details.fill_pack_features(data, history, today=TODAY, fetch=lambda url, accept: calls.append(url) or static,
                                          fetch_rendered=lambda urls: {url: rendered for url in urls}, sleep=lambda _: None)
        self.assertEqual(read, (2, 2))
        self.assertEqual(data["Tactics_Packs"][0]["pack_features"], ["Skateboard straps"])  # the menu isn't the description
        self.assertEqual(data["Zumiez_Packs"][0]["pack_features"], ["Water resistant", "Chest strap"])
        self.assertNotIn("pack_features", data["Tactics_Decks"][0])
        self.assertEqual(calls, ["https://www.tactics.com/vans/obstacle"])
        # Next run: saved features, no requests.
        fresh = self.data()
        again = details.fill_pack_features(fresh, history, today=TODAY + datetime.timedelta(days=1),
                                           fetch=lambda url, accept: self.fail(url),
                                           fetch_rendered=lambda urls: self.fail(urls), sleep=lambda _: None)
        self.assertEqual(again, (0, 0))
        self.assertEqual(fresh["Tactics_Packs"][0]["pack_features"], ["Skateboard straps"])

    def test_an_unreadable_page_is_tried_next_run(self):
        data, history = self.data(), self.history()
        details.fill_pack_features(data, history, today=TODAY, fetch=lambda url, accept: None,
                                   fetch_rendered=lambda urls: {}, sleep=lambda _: None)
        self.assertNotIn("pack_features_checked", history["https://www.tactics.com/vans/obstacle"])


if __name__ == "__main__":
    unittest.main()
