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
        self.assertIn('id="morePanel"', html)
        self.assertIn("Width range", html)
        self.assertLess(html.find('id="sizeFilters"'), html.find('id="morePanel"'))
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

    def test_filtered_cards_hide_and_brand_list_caps_at_seven(self):
        brands = [
            "Anti-Hero",
            "Baker",
            "Chocolate",
            "Creature",
            "Deathwish",
            "Element",
            "Girl",
            "Habitat",
        ]
        decks = [
            _deck("50.00", "https://example.com/%s" % index, "Zumiez", "%s Team Deck 8.0" % brand)
            for index, brand in enumerate(brands)
        ]
        html = build_report_html(
            {"Zumiez_Decks": decks},
            {},
            generated_at="2026-10-11T17:32:48+00:00",
        )
        style = html.split("<style>", 1)[1].split("</style>", 1)[0]
        self.assertRegex(
            style,
            r"\.deal-card\.filtered-out\s*,\s*\.deal-card\.grouped-hide\s*,\s*"
            r"tr\.deal-row\.filtered-out\s*,\s*tr\.deal-row\.grouped-hide\s*"
            r"\{[^}]*display:\s*none\s*!important",
        )
        self.assertRegex(style, r"#visitNote\[hidden\]\s*\{[^}]*display:\s*none\s*!important")
        self.assertGreater(style.rfind(".deal-card.filtered-out"), style.find(".deal-card {"))
        tail = style[style.rfind(".deal-card.filtered-out"):]
        self.assertNotRegex(tail, r"\.deal-card\s*\{[^}]*display:\s*flex")
        self.assertIn('id="visitNote" hidden', html)
        self.assertIn('id="brandFacet"', html)
        self.assertIn('id="brandSelect"', html)
        self.assertIn('data-cap="7"', html)
        self.assertIn('id="clearAll"', html)
        self.assertIn(">Clear all</button>", html)
        self.assertIn('id="brandMore" aria-expanded="false">Show more</button>', html)
        self.assertIn('class="facet-value" data-brand="Anti-Hero"', html)
        self.assertIn('class="facet-value is-extra" data-brand="Habitat"', html)
        self.assertIn("function rowMatches(row, overrides)", html)
        self.assertIn("function paintFacetCounts()", html)
        self.assertIn("minmax(176px, 1fr)", html)
        self.assertIn("-webkit-line-clamp: 3", html)
        self.assertIn('id="brandSearch"', html)
        self.assertIn("Counts match the other filters", html)
        self.assertIn("function paintSparklines()", html)
        self.assertIn("function sparkDirection(", html)
        self.assertIn('class="chip is-zero" data-range="10up"', html)
        self.assertIn("10.0+ (0)", html)

    def test_card_title_is_fixed_at_three_lines_and_missing_discount_is_neutral(self):
        deck = _deck(
            "39.99",
            "https://example.com/disney",
            "Zumiez",
            'Disney x HUF Mickey Mouse Worldwide Tour 8.25" Skateboard Deck',
        )
        hardware = {
            "name": 'Independent Black Crossbolts 1" Skateboard Hardware',
            "url": "https://example.com/bolts",
            "price_new": "3.95",
            "price_old": None,
            "part": "Bearings",
            "store": "Zumiez",
        }
        html = build_report_html(
            {"Zumiez_Decks": [deck], "Zumiez_Bearings": [hardware]},
            {},
            generated_at="2026-10-11T20:22:15+00:00",
        )
        style = html.split("<style>", 1)[1].split("</style>", 1)[0]
        self.assertIn("flex: 0 0 calc(1.25em * 3)", style)
        self.assertIn("line-clamp: 3", style)
        self.assertIn(".deal-card .card-title .product-link", style)
        self.assertNotIn(".card-title:hover .product-name", style)
        self.assertLess(
            style.find(".deal-card .product-name {"),
            style.find(".deal-card .card-title .product-link"),
        )
        cards = [
            part.split("</article>", 1)[0]
            for part in html.split('<article class="deal-card')[1:]
        ]
        card = next(part for part in cards if "Independent Black Crossbolts" in part)
        self.assertIn('class="discount card-off none"', card)
        self.assertIn("No discount info", card)
        self.assertNotIn(">N/A<", card)
        self.assertNotIn("card-off low", card)
        deck_card = next(part for part in cards if "Disney x HUF" in part)
        self.assertIn("card-off high", deck_card)
        self.assertNotIn("No discount info", deck_card)

    def test_nav_scan_label_and_brand_case_merge(self):
        low = _deck("50.00", "https://example.com/low", "Tactics", "5boro Lucky Candle Brooklyn 8.25 Skateboard Deck")
        high = _deck(
            "50.00",
            "https://example.com/high",
            "Zumiez",
            '5Boro Herrick 5Ball Video Series 8.25" Skateboard Deck',
        )
        html = build_report_html(
            {"Tactics_Decks": [low], "Zumiez_Decks": [high]},
            {},
            generated_at="2026-10-11T20:22:15+00:00",
        )
        self.assertIn("SkateDeals", html)
        self.assertIn('id="navDeals"', html)
        self.assertIn('id="navTrack"', html)
        self.assertIn('id="navInsights"', html)
        self.assertIn(">Deals</button>", html)
        self.assertIn(">Track</button>", html)
        self.assertIn(">Insights</button>", html)
        self.assertIn('id="lastScan" datetime="2026-10-11T20:22:15+00:00">', html)
        self.assertNotIn('id="lastScan" datetime="2026-10-11T20:22:15+00:00">2026-10-11T20:22:15+00:00<', html)
        self.assertIn(" ET</time>", html)
        self.assertNotIn('data-brand="5boro"', html)
        self.assertNotIn('value="5boro"', html)
        self.assertIn('data-brand="5Boro"', html)
        # Two table rows, two cards, and one brand facet button.
        self.assertEqual(html.count('data-brand="5Boro"'), 5)
        self.assertEqual(html.count('value="5Boro"'), 1)
        self.assertIn("const HISTORY_COLOR", html)
        self.assertIn("function brandSame(", html)

    def test_sidebar_rail_starts_with_the_board(self):
        """Search and filters share one grid row with the board.

        Two auto rows, with the board spanning both, grow the first row as the
        table gets taller and leave a blank gap above the sidebar.
        """
        deck = _deck("50.00", "https://example.com/deck", "Zumiez", "Powell Peralta Ripper 8.5 Skateboard Deck")
        html = build_report_html(
            {"Zumiez_Decks": [deck]},
            {},
            generated_at="2026-10-11T20:22:15+00:00",
        )
        style = html.split("<style>", 1)[1].split("</style>", 1)[0]
        self.assertIn('class="rail"', html)
        rail = html.split('<div class="rail">', 1)[1].split('<div class="board">', 1)[0]
        self.assertIn('id="searchInput"', rail)
        self.assertIn('id="filterDrawer"', rail)
        self.assertLess(html.find('<div class="rail">'), html.find('<div class="board">'))
        self.assertIn("width: 100%", style)
        self.assertIn("min-height: 100vh", style)
        self.assertNotIn("max-width: 1540px", style)
        self.assertIn("flex: 0 0 220px", style)
        self.assertIn("flex: 1 1 auto", style)
        self.assertIn("min-width: 0", style)
        self.assertIn(".rail .sidebar", style)
        self.assertLess(style.find(".rail {"), style.find(".rail .sidebar"))
        rail_css = style[style.find(".rail {"):style.find(".rail .sidebar")]
        self.assertIn("position: sticky", rail_css)
        sidebar_css = style[style.find(".rail .sidebar"):style.find(".rail .sidebar") + 500]
        self.assertIn("position: static", sidebar_css)
        self.assertIn("overflow: auto", sidebar_css)

    def test_filter_sections_remember_and_chart_points_are_labeled(self):
        deck = _deck("50.00", "https://example.com/deck", "Zumiez", "Powell Peralta Ripper 8.5 Skateboard Deck")
        html = build_report_html(
            {"Zumiez_Decks": [deck]},
            {},
            generated_at="2026-10-11T20:22:15+00:00",
        )
        self.assertIn('class="filter-section is-open" data-section="brand"', html)
        self.assertIn('class="filter-section is-open" data-section="width"', html)
        self.assertIn('class="filter-section" data-section="store"', html)
        self.assertIn('class="filter-section" data-section="type"', html)
        self.assertIn('class="filter-section" data-section="price"', html)
        self.assertIn('class="filter-section" data-section="discount"', html)
        self.assertIn('class="filter-section" data-section="score"', html)
        self.assertNotIn('class="filter-section is-open" data-section="store"', html)
        self.assertIn("salesscraper2.filterSections", html)
        self.assertIn("function restoreFilterSections(", html)
        self.assertIn("function rememberFilterSections(", html)
        self.assertIn("function chartHitLabel(", html)
        self.assertIn("function nearestChartHit(", html)
        nearest = html.split("function nearestChartHit(", 1)[1].split("function paintFilterSection(", 1)[0]
        self.assertIn("hit.y", nearest)
        self.assertIn("Math.hypot", nearest)
        self.assertIn("Price reduction · ", html)
        self.assertIn("function paintResultCount(", html)


if __name__ == "__main__":
    unittest.main()
