"""Report wiring for charts, cards, filters, scores, and deals intelligence."""

import json
import unittest

from report import build_report_html


def _deck(price, url, store, name):
    return {
        "name": name,
        "url": url,
        "price_new": price,
        "price_old": "80.00",
        "part": "Decks",
        "store": store,
        "image": "https://example.com/deck.jpg",
    }


class ReportExtraTests(unittest.TestCase):
    def test_page_has_the_new_views_and_a_combined_chart(self):
        left = _deck("64.99", "https://example.com/z", "Zumiez", "Baker Figgy Divine Evil Deck 8.125")
        right = _deck("44.99", "https://example.com/s", "SkateWarehouse", "Baker Figgy Divine Evil Deck 8.12 x 31.875")
        history = {
            left["url"]: {
                "name": left["name"],
                "store": "Zumiez",
                "part": "Decks",
                "first_seen": "2026-07-20",
                "last_seen": "2026-09-30",
                "observation_count": 3,
                "all_time_low": 64.99,
                "all_time_low_date": "2026-08-14",
                "prices": {"2026-07-20": 74.95, "2026-08-14": 64.99, "2026-09-30": 64.99},
            },
            right["url"]: {
                "name": right["name"],
                "store": "SkateWarehouse",
                "part": "Decks",
                "first_seen": "2026-07-20",
                "last_seen": "2026-09-30",
                "observation_count": 4,
                "all_time_low": 44.99,
                "all_time_low_date": "2026-09-28",
                "prices": {"2026-07-20": 74.95, "2026-09-28": 44.99, "2026-09-29": 44.99, "2026-09-30": 44.99},
            },
        }
        html = build_report_html(
            {"Zumiez_Decks": [left], "SkateWarehouse_Decks": [right]},
            {},
            price_history=history,
            generated_at="2026-09-30T12:56:14+00:00",
        )
        self.assertIn('id="productModal"', html)
        self.assertIn('data-window="30"', html)
        self.assertIn('data-window="90"', html)
        self.assertIn('data-window="180"', html)
        self.assertIn('id="cardGrid"', html)
        self.assertIn('id="layoutCards"', html)
        self.assertIn('id="activeChips"', html)
        self.assertIn("are not added", html)
        self.assertIn("score-btn score-", html)
        self.assertIn("On sale", html)
        self.assertIn("at least 30%", html)
        self.assertIn("Deals intelligence", html)
        self.assertIn('id="freshness"', html)
        self.assertIn('id="filterDrawer"', html)
        self.assertIn('id="filtersOpen"', html)
        self.assertIn('id="baselineSelect"', html)
        self.assertIn('id="scoreMin"', html)
        self.assertIn("Today's highlights", html)
        self.assertIn("Zumiez (", html)
        self.assertNotIn('class="store-strip"', html)
        more = html.split('id="morePanel"', 1)[1]
        self.assertIn("Width range", more.split("</div>", 1)[0] + more)
        self.assertLess(html.find('id="morePanel"'), html.find('id="sizeFilters"'))
        payload = html.split('id="catalogJson">', 1)[1].split("</script>", 1)[0]
        data = json.loads(payload)
        series = None
        for item in data["items"].values():
            rows = item.get("seriesList") or []
            if len(rows) >= 2:
                series = rows
                break
        self.assertIsNotNone(series)
        stores = {row["store"] for row in series}
        self.assertEqual(stores, {"Zumiez", "SkateWarehouse"})
        self.assertTrue(any(marker["kind"] == "drop" for row in series for marker in row["markers"]))
        self.assertNotIn("Shipping", html)


if __name__ == "__main__":
    unittest.main()
