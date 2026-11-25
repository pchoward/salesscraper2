"""Store links open on the sale variant we list (owner, 2026-11-25).

evo's Fox Racing PureVue Goggles were listed at $80.95 (a sale color), but the
plain product page opens on Black/Clear at $159.95. Shopify listings now carry
``link`` (``?variant=<id>``) when the page's first variant isn't the one we
list. ``url`` stays the listing's identity.
"""

import unittest

import matching
import notify
import page
import sports
from sports.mtb import stores as mtb_stores
from stores import shopify

URL = "https://www.evo.com/products/247562-fox-racing-purevue-goggles"


def goggles(first_on_sale=False):
    full = {"id": 111, "title": "Black/Clear", "price": "159.95", "compare_at_price": None, "available": True}
    sale = {"id": 222, "title": "Gold", "price": "80.95", "compare_at_price": "159.95", "available": True}
    return {"handle": "247562-fox-racing-purevue-goggles", "title": "PureVue Goggles", "vendor": "Fox Racing",
            "product_type": "Bike Goggles", "tags": [],
            "variants": [sale, full] if first_on_sale else [full, sale]}


class VariantLinkTests(unittest.TestCase):
    def listing(self, product):
        with sports.SPORTS["mtb"].session():
            items = shopify.ShopifyScraper(mtb_stores.EVO, "Protection").products_from([product])
        self.assertEqual(len(items), 1)
        return items[0]

    def test_links_to_the_sale_variant_when_the_page_opens_on_another(self):
        item = self.listing(goggles())
        self.assertEqual(item["url"], URL)  # identity unchanged
        self.assertEqual(item["link"], URL + "?variant=222")
        self.assertEqual(item["price_new"], "80.95")

    def test_no_link_when_the_page_already_opens_on_it(self):
        self.assertNotIn("link", self.listing(goggles(first_on_sale=True)))

    def test_skips_sold_out_first_variant(self):
        product = goggles()
        product["variants"][0]["available"] = False  # page opens on the next buyable one: the sale one
        self.assertNotIn("link", self.listing(product))

    def test_helper_edges(self):
        product = goggles()
        sale = product["variants"][1]
        self.assertEqual(shopify.variant_link(product, URL + "?variant=9", sale), "")  # deck width split
        self.assertEqual(shopify.variant_link(product, URL, {"id": None}), "")
        self.assertEqual(shopify.variant_link({"variants": []}, URL, sale), "")


class LinkUseTests(unittest.TestCase):
    ITEM = {"name": "Fox Racing PureVue Goggles", "store": "evo", "url": URL, "link": URL + "?variant=222",
            "price_new": "80.95", "price_old": "159.95", "part": "Protection"}

    def test_page_and_email_links_use_it(self):
        self.assertEqual(page.shop_href(self.ITEM), URL + "?variant=222")
        self.assertEqual(page.shop_href(dict(self.ITEM, link="")), URL)
        self.assertIn('href="' + URL + '?variant=222"', page._product_link(self.ITEM))
        self.assertEqual(notify._product_url(self.ITEM), URL + "?variant=222")
        self.assertEqual(notify._product_url(dict(self.ITEM, link=None)), URL)

    def test_matched_offers_keep_both(self):
        evo = dict(self.ITEM, name="Fox Racing PureVue Roll Off Goggles", brand="Fox Racing")
        other = dict(evo, store="Bikes Online", url="https://bikesonline.example/products/purevue", price_new="99.95")
        other.pop("link")
        with sports.SPORTS["mtb"].session():
            groups = matching.sport_groups([evo, other], apply_filters=False)
        offers = {offer["store"]: offer for group in groups for offer in group["offers"]}
        self.assertEqual(offers["evo"]["url"], URL)  # matching and history still key on url
        self.assertEqual(offers["evo"]["link"], URL + "?variant=222")
        self.assertNotIn("link", offers["Bikes Online"])
        self.assertIn(URL + "?variant=222", page._offer_link(dict(offers["evo"], currency="USD")))


if __name__ == "__main__":
    unittest.main()
