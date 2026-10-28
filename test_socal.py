"""SoCal Skateshop (Miva): clearance cards, paging with the crawl delay, parts from names."""

import unittest
from pathlib import Path

from stores import socal
from stores.registry import build_scrapers


def card(href, name, was, now, image="graphics/00000001/42/deck_280x280.jpg"):
    # The markup of one .x-product-list__item from the owner's capture (2026-10-28).
    was_html = f'<span class="x-product-list__price u-color-gray-30"><s>${was}</s></span>' if was else ""
    return f"""
<div id="js-inc-plst-product" class="o-layout__item u-text-center x-product-list__item">
  <a class="u-block x-product-list__link" href="https://socalskateshop.com/{href}" title="{name}">
    <figure class="x-product-list__figure"><div class="x-product-list__image-container">
      <div class="product-flag"><img src="graphics/00000001/clearance.gif" alt="Clearance Product" /></div>
      <img class="u-block x-product-list__image" src="{image}" alt="{name}">
    </div>
    <figcaption><strong class="x-product-list__name">{name}</strong>
      {was_html}<span class="x-product-list__price u-color-red">${now}</span></figcaption></figure>
  </a>
  <form action="https://socalskateshop.com/basket-contents.html"></form>
</div>"""


def page(cards):
    return ('<html><body><section class="o-layout u-grids-2 u-grids-4--l x-product-list">'
            + "".join(cards) + "</section></body></html>")


CARDS = [
    card("Poorhouse-Pop-Skateboard-Deck-Black-Stain-8-5x32-375.html", "8.5x32.375 Poorhouse Pop Deck - Black Stain", "49.95", "34.97"),
    card("Bones-STF-54mm.html", "Bones STF V5 Sidecut 54mm 99a Wheels", "44.95", "29.97"),
    card("Penny-Cruiser.html", "Penny 22in Cruiser Complete", "99.95", "59.97"),
    card("Triple-Eight-Helmet.html", "Triple Eight Sweatsaver Helmet - Large", "54.95", "38.47"),
    card("No-Markdown-Deck.html", "8.25 Some Brand Deck", None, "39.95"),
    card("SoCal-Tee.html", "SoCal Skateshop Logo T-Shirt", "24.95", "14.97"),
]


class SoCalTests(unittest.TestCase):
    def test_cards_read_name_link_prices_and_image(self):
        cards = socal.cards_from_html(page(CARDS))
        self.assertEqual(len(cards), 6)
        first = cards[0]
        self.assertEqual(first["name"], "8.5x32.375 Poorhouse Pop Deck - Black Stain")
        self.assertEqual(first["url"], "https://socalskateshop.com/Poorhouse-Pop-Skateboard-Deck-Black-Stain-8-5x32-375.html")
        self.assertEqual((first["price_new"], first["price_old"]), ("34.97", "49.95"))
        self.assertEqual(first["image"], "https://socalskateshop.com/graphics/00000001/42/deck_280x280.jpg")
        self.assertIsNone(cards[4]["price_old"])

    def test_parts_from_names_and_markdowns_only(self):
        cards = socal.cards_from_html(page(CARDS))
        found = {part: [i["name"] for i in socal.SoCalScraper(part).products_from(cards)] for part in socal.PARTS}
        self.assertEqual(found["Decks"], ["8.5x32.375 Poorhouse Pop Deck - Black Stain"])
        self.assertEqual(found["Wheels"], ["Bones STF V5 Sidecut 54mm 99a Wheels"])
        self.assertEqual(found["Completes"], [], "a Penny cruiser is not a street complete")
        self.assertEqual(found["Protection"], ["Triple Eight Sweatsaver Helmet - Large"])
        everything = sum(found.values(), [])
        self.assertNotIn("8.25 Some Brand Deck", everything, "no struck-through regular price, no markdown")
        self.assertNotIn("SoCal Skateshop Logo T-Shirt", everything)
        deck = socal.SoCalScraper("Decks").products_from(cards)[0]
        self.assertEqual((deck["size"], deck["length"]), ("8.5", 32.375))
        helmet = socal.SoCalScraper("Protection").products_from(cards)[0]
        self.assertEqual((helmet["protection_type"], helmet["protection_sizes"]), ("Helmet", ["L"]))

    def test_pages_of_72_with_the_crawl_delay(self):
        full = [card(f"deck-{n}.html", f"Deck {n}", "50.00", "40.00") for n in range(socal.PER_PAGE)]
        pages = {0: page(full), socal.PER_PAGE: page(CARDS)}
        asked, pauses = [], []

        def fetch(url):
            asked.append(url)
            offset = int(url.split("Offset=")[2].split("&")[0])
            return pages[offset]

        cards = socal.load_clearance(fetch, sleep=pauses.append)
        self.assertEqual(len(cards), socal.PER_PAGE + len(CARDS))
        self.assertEqual(asked, [socal.page_url(0), socal.page_url(72)])
        self.assertIn("Per_Page=72", asked[0])
        self.assertEqual(pauses, [5], "robots.txt asks for 5 seconds between requests")

    def test_a_failed_page_fails_the_run_and_repeats_stop(self):
        self.assertIsNone(socal.load_clearance(lambda url: None, sleep=lambda _s: None))
        full = [card(f"deck-{n}.html", f"Deck {n}", "50.00", "40.00") for n in range(socal.PER_PAGE)]
        asked = []
        cards = socal.load_clearance(lambda url: asked.append(url) or page(full), sleep=lambda _s: None)
        self.assertEqual(len(cards), socal.PER_PAGE)
        self.assertEqual(len(asked), 2, "a page of only repeats ends the crawl")

    def test_wiring(self):
        self.assertEqual({s.part for s in build_scrapers() if s.name == "SoCal"}, set(socal.PARTS))
        root = Path(__file__).resolve().parent
        self.assertIn('socal: "SoCal"', (root / "page.js").read_text(encoding="utf-8"))
        from alerts_delivery import STORE_HOSTS
        self.assertIn("socalskateshop.com", STORE_HOSTS)


if __name__ == "__main__":
    unittest.main()
