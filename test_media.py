"""Listing images and the fields stored on price history."""

import unittest

from bs4 import BeautifulSoup

from history import prune_price_history, update_price_history
from media import attach_listing_media, extract_image_url


class MediaTests(unittest.TestCase):
    def test_prefers_real_image_over_placeholder(self):
        html = """
        <li class="ProductCard">
          <img src="https://cdn.example.com/placeholder.gif" data-src="//cdn.example.com/deck.jpg">
        </li>
        """
        node = BeautifulSoup(html, "html.parser").li
        self.assertEqual(extract_image_url(node, "https://www.zumiez.com"), "https://cdn.example.com/deck.jpg")

    def test_relative_and_missing(self):
        html = '<div class="product-item"><img src="/cdn/shop/deck.jpg" alt="Baker"></div>'
        node = BeautifulSoup(html, "html.parser").div
        self.assertEqual(
            extract_image_url(node, "https://shop.ccs.com"),
            "https://shop.ccs.com/cdn/shop/deck.jpg",
        )
        self.assertEqual(extract_image_url(BeautifulSoup("<div></div>", "html.parser").div, ""), "")

    def test_parent_image_and_wheelbase_land_on_the_item(self):
        html = """
        <div class="card">
          <img src="https://www.skatewarehouse.com/images/caster.jpg" alt="Caster">
          <a href="/caster">Anti-Hero Caster Deck 8.62 Wheelbase 14.25</a>
        </div>
        """
        anchor = BeautifulSoup(html, "html.parser").a
        item = {
            "name": "Anti-Hero Caster Deck 8.62",
            "url": "https://www.skatewarehouse.com/caster",
            "price_new": "54.95",
            "price_old": "74.95",
            "part": "Decks",
            "store": "SkateWarehouse",
        }
        attach_listing_media(item, anchor, "https://www.skatewarehouse.com")
        self.assertEqual(item["image"], "https://www.skatewarehouse.com/images/caster.jpg")
        self.assertEqual(item["width"], 8.62)
        self.assertEqual(item["wheelbase"], 14.25)

    def test_history_keeps_the_image(self):
        item = {
            "name": "Baker Team Deck 8.25",
            "url": "https://example.com/baker",
            "price_new": "40.00",
            "price_old": "70.00",
            "part": "Decks",
            "store": "Zumiez",
            "image": "https://cdn.example.com/baker.jpg",
            "width": 8.25,
        }
        history = update_price_history({"Zumiez_Decks": [item]}, {}, today="2026-09-30")
        entry = history["https://example.com/baker"]
        self.assertEqual(entry["image"], "https://cdn.example.com/baker.jpg")
        self.assertEqual(entry["width"], 8.25)
        pruned, _stats = prune_price_history(history, today="2026-09-30", current_data={"Zumiez_Decks": [item]})
        self.assertEqual(pruned["https://example.com/baker"]["image"], "https://cdn.example.com/baker.jpg")


if __name__ == "__main__":
    unittest.main()
