"""Report wiring for charts, cards, filters, scores, and deals intelligence."""

import json
import subprocess
import unittest
from pathlib import Path

from page import _atl_section, _gone_section
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
        self.assertIn('id="quickView"', html)
        self.assertNotIn('id="productModal"', html)
        self.assertNotIn('id="priceDrawer"', html)
        self.assertNotIn(">Close</button>", html)
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
        self.assertIn('id="emptyState"', html)
        self.assertNotIn('id="baselineSelect"', html)
        self.assertIn('id="scoreMin"', html)
        self.assertNotIn("Today's highlights", html)
        self.assertIn('data-kind="highlights"', html)
        self.assertIn(">Highlights", html)
        self.assertIn("Zumiez (", html)
        self.assertNotIn('class="store-strip"', html)
        self.assertIn('id="morePanel"', html)
        self.assertIn("Deck Width", html)
        self.assertIn('id="sizeFilters"', html)
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
        self.assertRegex(style, r"\.empty-state\[hidden\]\s*\{[^}]*display:\s*none\s*!important")
        self.assertGreater(style.rfind(".deal-card.filtered-out"), style.find(".deal-card {"))
        tail = style[style.rfind(".deal-card.filtered-out"):]
        self.assertNotRegex(tail, r"\.deal-card\s*\{[^}]*display:\s*flex")
        self.assertIn('id="emptyState" class="empty-state" hidden', html)
        self.assertNotIn('id="visitNote"', html)
        self.assertIn('id="brandFacet"', html)
        self.assertIn('id="brandSelect"', html)
        self.assertIn('id="clearAll"', html)
        self.assertIn(">Clear all</button>", html)
        self.assertNotIn("Show more", html)
        self.assertNotIn('id="brandMore"', html)
        self.assertIn('id="brandList" tabindex="0"', html)
        self.assertIn("max-height: 200px", html)
        self.assertIn('class="facet-value" data-brand="Anti-Hero"', html)
        self.assertIn('class="facet-value" data-brand="Habitat"', html)
        self.assertNotIn("is-extra", html)
        self.assertIn("function rowMatches(row, overrides)", html)
        self.assertIn("function paintFacetCounts()", html)
        self.assertNotIn("minmax(176px, 1fr)", html)
        self.assertIn("minmax(170px, 1fr)", html)
        self.assertNotIn("@container deals (min-width: 1092px)", html)
        prices = html.split(".card-prices {", 1)[1].split("}", 1)[0]
        self.assertIn("flex-wrap: wrap", prices)
        now = html.split(".now-price {", 1)[1].split("}", 1)[0]
        self.assertIn("font-weight: 800", now)
        self.assertIn("white-space: nowrap", now)
        self.assertIn("max-width: 100%", html.split(".avg-price {", 1)[1].split("}", 1)[0])
        self.assertIn("-webkit-line-clamp: 2", html)
        self.assertIn('id="brandSearch"', html)
        self.assertNotIn("Counts match current results", html)
        self.assertIn("function paintSparklines()", html)
        self.assertIn("let catalogData = null", html)
        self.assertIn("function refreshCharts()", html)
        self.assertIn("function queueFilters()", html)
        self.assertNotIn("paintSparklines();\n    paintCardStats();", html)
        self.assertIn("function sparkDirection(", html)
        self.assertIn('data-buckets="10up"', html)
        self.assertIn('class="chip width-chip is-zero"', html)
        self.assertIn(">10+</span>", html)

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
        self.assertIn("line-clamp: 2", style)
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
        self.assertIn("No list price", card)
        self.assertNotIn(">N/A<", card)
        self.assertNotIn("card-off low", card)
        deck_card = next(part for part in cards if "Disney x HUF" in part)
        self.assertIn("card-off high", deck_card)
        self.assertNotIn("No list price", deck_card)

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
        self.assertIn('id="searchInput"', html)
        self.assertLess(html.find('id="searchInput"'), html.find('<div class="rail">'))
        self.assertNotIn('id="searchInput"', rail)
        self.assertIn('id="filterDrawer"', rail)
        self.assertLess(html.find('<div class="rail">'), html.find('<div class="board">'))
        self.assertIn("width: 100%", style)
        self.assertIn("min-height: 100vh", style)
        self.assertNotIn("max-width: 1540px", style)
        self.assertIn("flex: 0 0 200px", style)
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
        self.assertIn('class="filter-section" data-section="deals"', html)
        self.assertNotIn('class="filter-section is-open" data-section="deals"', html)
        self.assertIn('class="filter-section" data-section="interval"', html)
        self.assertNotIn('data-section="store"', html)
        self.assertNotIn('data-section="type"', html)
        self.assertIn('id="storeFilters"', html)
        self.assertIn('id="partFilters"', html)
        self.assertIn('id="navPills"', html)
        self.assertIn('data-store="all"', html)
        self.assertIn(">All stores<", html)
        self.assertIn(
            'data-part="Decks" data-count="1" aria-pressed="true"',
            html,
        )
        self.assertIn('class="sr-only" aria-label="Store"', html)
        self.assertIn('class="sr-only" aria-label="Product type"', html)
        self.assertIn('id="moreStores" hidden', html)
        self.assertIn('id="moreParts" hidden', html)
        self.assertIn('data-order="0" data-home="row" data-store="all"', html)
        self.assertIn('data-order="0" data-home="row" data-part="all"', html)
        rail = html.split('<div class="rail">', 1)[1].split('<div class="board">', 1)[0]
        self.assertNotIn('id="storeFilters"', rail)
        self.assertNotIn('id="partFilters"', rail)
        self.assertNotIn("quick-chip", rail)
        self.assertNotIn(">All stores<", rail)
        self.assertNotIn(">Stores<", rail)
        self.assertNotIn(">Products<", rail)
        style = html.split("<style>", 1)[1].split("</style>", 1)[0]
        nav_css = style.split(".nav-row {", 1)[1].split("}", 1)[0]
        self.assertIn("flex-wrap: nowrap", nav_css)
        self.assertIn("function nextNavOverflow(", html)
        self.assertIn("function fitNavPills(", html)
        self.assertIn("#filtersOpen { display: inline-flex", style)
        self.assertNotIn(".filters-open { display: inline-flex", style)
        self.assertIn("body.filters-open", style)
        self.assertIn('id="productSpecs"', html)
        self.assertIn("Pick a spec to switch to that product type.", html)
        self.assertIn('class="filter-section is-open" data-section="brand"', html)
        self.assertIn(
            'class="filter-section is-open" data-section="width" data-for="Decks"',
            html,
        )
        self.assertNotIn('is-type-hidden" data-section="width"', html)
        self.assertIn('class="filter-section" data-section="price"', html)
        self.assertIn('class="filter-section" data-section="discount"', html)
        self.assertIn('data-section="score"', html)
        self.assertIn(">Deal quality<", html)
        self.assertIn('class="filter-section" data-section="views"', html)
        self.assertIn('data-section="watching"', html)
        self.assertIn('data-section="bookmarks"', html)
        self.assertLess(html.find('id="navPills"'), html.find('id="changeLine"'))
        self.assertLess(html.find('id="changeLine"'), html.find('<div class="rail">'))
        self.assertLess(html.find('id="partFilters"'), html.find('id="storeFilters"'))
        self.assertLess(html.find('id="partFilters"'), html.find('id="contextSpecs"'))
        self.assertLess(html.find('data-section="width"'), html.find('id="productSpecs"'))
        self.assertLess(html.find('id="productSpecs"'), html.find('data-section="brand"'))
        self.assertLess(html.find('data-section="brand"'), html.find('data-section="price"'))
        self.assertLess(html.find('data-section="price"'), html.find('data-section="score"'))
        self.assertLess(html.find('data-section="score"'), html.find('data-section="deals"'))
        self.assertIn('id="specGroup"', html)
        self.assertIn('aria-label="Shopping filters"', html)
        self.assertIn('aria-label="Deal intelligence"', html)
        self.assertIn('aria-label="Personal tools"', html)
        self.assertIn("function activeSpecKeys(", html)
        self.assertIn("Historical low", html)
        self.assertIn('aria-label="Score breakdown"', html)
        self.assertLess(html.find('data-section="deals"'), html.find('data-section="interval"'))
        self.assertIn("function syncTypeSections(", html)
        self.assertIn(".filter-section.is-type-hidden", html)
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

    def test_keepa_card_uses_tracked_prices_and_drop_interval(self):
        deck = _deck(
            "40.00",
            "https://example.com/drop",
            "Zumiez",
            "Powell Peralta Ripper 8.5 Skateboard Deck",
        )
        wheel = {
            "name": "Bones STF 53mm Skateboard Wheels",
            "url": "https://example.com/bones",
            "price_new": "30.00",
            "price_old": "40.00",
            "part": "Wheels",
            "store": "Zumiez",
        }
        history = {
            deck["url"]: {
                "name": deck["name"],
                "store": "Zumiez",
                "part": "Decks",
                "first_seen": "2026-09-01",
                "last_seen": "2026-10-11",
                "prices": {
                    "2026-09-01": 60.0,
                    "2026-10-01": 50.0,
                    "2026-10-04": 40.0,
                    "2026-10-11": 40.0,
                },
            },
            wheel["url"]: {
                "name": wheel["name"],
                "store": "Zumiez",
                "part": "Wheels",
                "first_seen": "2026-10-02",
                "last_seen": "2026-10-11",
                "prices": {"2026-10-02": 30.0, "2026-10-11": 30.0},
            },
        }
        html = build_report_html(
            {"Zumiez_Decks": [deck], "Zumiez_Wheels": [wheel]},
            {},
            price_history=history,
            generated_at="2026-10-11T21:46:35+00:00",
        )
        card = next(
            part.split("</article>", 1)[0]
            for part in html.split('<article class="deal-card')[1:]
            if "https://example.com/drop" in part
        )
        self.assertIn("Now $40.00", card)
        self.assertIn("Average $47.50", card)
        self.assertNotIn("Dropped from $50.00 on Oct 4", card)
        self.assertNotIn("Price since Oct 4", card)
        self.assertIn('data-dropday="2026-10-04"', card)
        self.assertIn("spark-card", card)
        self.assertIn('height="30"', card)
        self.assertNotIn("quiet-low", card)
        self.assertNotIn("Verified low", card)
        self.assertNotIn("LOWEST EVER", card)
        self.assertNotIn("New low", card)
        self.assertNotIn("pill-lowest", card)
        self.assertNotIn("pill-hot", card)
        flat = next(
            part for part in html.split('<article class="deal-card')[1:] if "example.com/bones" in part
        ).split("</article>", 1)[0]
        self.assertNotIn("Price unchanged since Oct 2", flat)
        self.assertIn("Now $30.00", flat)
        self.assertNotIn("At lowest tracked price", flat)
        self.assertNotIn("Verified low", flat)
        self.assertNotIn("New low", flat)
        self.assertIn('class="avg-price" data-symbol="$"', flat)
        self.assertNotIn('class="avg-price" data-symbol="$" hidden', flat)
        self.assertIn('height="12"', flat)
        self.assertNotIn('id="categoryStrip"', html)
        self.assertIn('id="partFilters"', html)
        self.assertIn('data-part="Decks"', html)
        self.assertIn('data-part="Wheels"', html)
        self.assertNotIn('data-part="Trucks"', html)
        self.assertIn('id="dropInterval"', html)
        self.assertIn(">Day <", html)
        self.assertIn(">3 Months <", html)
        self.assertIn('data-kind="new"', html)
        self.assertIn('data-kind="hot"', html)
        self.assertIn("kind-drop", html)
        self.assertIn("Bookmark this selection", html)
        self.assertIn('id="discountMax"', html)
        self.assertIn("Any price", html)
        self.assertIn("function dropInInterval(", html)
        self.assertIn("function syncDuals(", html)

    def test_highlights_view_uses_digest_lists_and_width_groups_are_truthful(self):
        fresh = _deck("40.00", "https://example.com/fresh", "Zumiez", "Baker Brand Logo 8.5 Skateboard Deck")
        older = _deck("50.00", "https://example.com/older", "Zumiez", "Girl Gass 8.0 Skateboard Deck")
        html = build_report_html(
            {"Zumiez_Decks": [fresh, older]},
            {"Zumiez_Decks": [{"type": "new", "item": fresh}]},
            generated_at="2026-10-11T21:46:35+00:00",
        )
        self.assertIn('data-kind="highlights"', html)
        self.assertLess(html.find('id="dealTypes"'), html.find('data-kind="highlights"'))
        def row_for(url):
            return next(part for part in html.split("<tr ") if url in part)
        self.assertIn('data-highlight="1"', row_for("https://example.com/fresh"))
        self.assertIn('data-highlight="0"', row_for("https://example.com/older"))
        self.assertIn("if (highlights && row.dataset.highlight !== \"1\") return false;", html)
        self.assertNotIn("<summary>Today's highlights</summary>", html)
        self.assertIn("Deal Type", html)
        self.assertIn(">Products<", html)
        self.assertIn("Saved Views", html)
        self.assertIn(">Show results</button>", html)
        self.assertIn("function adoptSpecPart(", html)
        self.assertIn('id="groupToggle"', html)
        self.assertLess(html.find('id="groupToggle"'), html.find('<div class="rail">'))

    def test_new_low_is_loud_and_verified_low_stays_quiet(self):
        deck = _deck("40.00", "https://example.com/newlow", "Zumiez", "Powell Peralta Ripper 8.5 Skateboard Deck")
        history = {
            deck["url"]: {
                "name": deck["name"],
                "store": "Zumiez",
                "part": "Decks",
                "first_seen": "2026-09-01",
                "last_seen": "2026-10-11",
                "prices": {
                    "2026-09-01": 60.0,
                    "2026-10-01": 50.0,
                    "2026-10-11": 40.0,
                },
            }
        }
        html = build_report_html(
            {"Zumiez_Decks": [deck]},
            {
                "Zumiez_Decks": [{
                    "type": "price_drop",
                    "item": deck,
                    "old": "50.00",
                    "new": "40.00",
                    "delta": 10,
                    "percent_vs_prior": 20,
                }]
            },
            price_history=history,
            generated_at="2026-10-11T21:46:35+00:00",
        )
        card = html.split("https://example.com/newlow", 1)[1].split("</article>", 1)[0]
        self.assertIn("pill-newlow", card)
        self.assertIn(">New low<", card)
        self.assertNotIn("Verified low", card)
        self.assertIn('data-kind="highlights"', html)

    def test_nav_overflow_keeps_all_and_the_selected_chip(self):
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        start = source.find("function nextNavOverflow(")
        end = source.find("function navClusters(")
        self.assertGreater(start, 0)
        self.assertGreater(end, start)
        script = source[start:end] + """
const chip = (value, pressed) => ({value: value, pressed: !!pressed});
const stores = {chips: ["all","Zumiez","Tactics","SkateWarehouse","CCS"].map(value => chip(value, value === "all"))};
const products = {chips: ["all","Decks","Trucks","Wheels"].map(value => chip(value, value === "Decks"))};
let pick = nextNavOverflow([stores, products]);
if (!pick || pick.cluster !== 1 || products.chips[pick.index].value !== "Wheels") {
    throw new Error("expected Wheels first, got " + JSON.stringify(pick));
}
products.chips = ["all","Decks","Trucks","Wheels"].map(value => chip(value, value === "Wheels"));
pick = nextNavOverflow([stores, products]);
if (!pick || products.chips[pick.index].value !== "Trucks") {
    throw new Error("expected Trucks before a pressed Wheels chip");
}
products.chips = ["all","Decks"].map(value => chip(value, value === "Decks"));
pick = nextNavOverflow([stores, products]);
if (!pick || pick.cluster !== 0 || stores.chips[pick.index].value !== "CCS") {
    throw new Error("expected CCS once products cannot shrink");
}
stores.chips = [chip("all", true)];
products.chips = [chip("all", false), chip("Decks", true)];
        if (nextNavOverflow([stores, products]) !== null) {
    throw new Error("All and the selected chip stay on the row");
}
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_hidden_category_specs_do_not_apply(self):
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        start = source.find("function activeSpecKeys(")
        end = source.find("function specKeyActive(")
        self.assertGreater(start, 0)
        self.assertGreater(end, start)
        script = source[start:end] + """
function same(left, right) {
  if (left.length !== right.length) return false;
  return left.every((value, index) => value === right[index]);
}
if (!same(activeSpecKeys("Decks"), ["widths", "length", "wheelbase"])) throw new Error("decks");
if (!same(activeSpecKeys(), ["widths", "length", "wheelbase"])) throw new Error("default decks");
if (!same(activeSpecKeys("Wheels"), ["diameters", "duros", "shapes"])) throw new Error("wheels");
if (!same(activeSpecKeys("Trucks"), ["truckSizes", "truckHeights", "constructions"])) throw new Error("trucks");
if (!same(activeSpecKeys("Bearings"), ["abecs"])) throw new Error("bearings");
if (!same(activeSpecKeys("Sneakers"), ["shoeSizes"])) throw new Error("sneakers");
if (activeSpecKeys("Accessories").length) throw new Error("accessories hide specs");
if (activeSpecKeys("all").length) throw new Error("all types hide category specs");
const body = `%s`;
if (body.indexOf("specKeyActive(\\"widths\\", viewPart)") < 0) throw new Error("width gate");
if (body.indexOf("specKeyActive(\\"length\\", viewPart)") < 0) throw new Error("length gate");
if (body.indexOf("if (!specKeyActive(facet.stateKey, viewPart)) continue;") < 0) throw new Error("spec gate");
""" % source[source.find("function rowMatches("):source.find("function syncDetails(")]
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_gone_and_atl_tables_sort_and_filter(self):
        dear = {
            "name": "Independent Stage 11 Truck",
            "url": "https://example.com/truck",
            "price_new": "48.00",
            "part": "Trucks",
            "store": "Tactics",
            "_brand": "Independent",
        }
        cheap = {
            "name": "Baker Logo 8.0 Deck",
            "url": "https://example.com/cheap",
            "price_new": "19.00",
            "part": "Decks",
            "store": "CCS",
            "_brand": "Baker",
        }
        atl = _atl_section([dear, cheap], {})
        self.assertIn("sortSection('atlTable','price')", atl)
        self.assertLess(atl.index('data-price="48.00"'), atl.index('data-price="19.00"'))
        self.assertIn('data-store="CCS"', atl)
        self.assertIn('data-part="Trucks"', atl)
        self.assertIn('data-brand="Independent"', atl)
        history = {
            "https://example.com/gone-deck": {
                "name": "Chocolate Anderson Jazz Lovers 8.5 Skateboard Deck",
                "store": "Zumiez",
                "part": "Decks",
                "last_seen": "2026-09-20",
                "miss_streak": 2,
                "prices": {"2026-09-20": 49.99},
                "stock": "out_of_stock",
            },
            "https://example.com/gone-wheel": {
                "name": "Spitfire Formula Four 54mm Wheels",
                "store": "Tactics",
                "part": "Wheels",
                "last_seen": "2026-09-21",
                "miss_streak": 2,
                "prices": {"2026-09-21": 24},
            },
        }
        gone = _gone_section(history, {}, "2026-09-22", [])
        self.assertIn("sortSection('goneTable','price')", gone)
        self.assertIn('data-price="49.99"', gone)
        self.assertIn('data-price="24.00"', gone)
        self.assertIn('data-brand="Chocolate"', gone)
        self.assertIn('data-store="Tactics"', gone)
        self.assertIn("SOLD OUT", gone)
        self.assertIn("NO LONGER LISTED", gone)
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        compare = source[source.find("const SORT_NUMERIC"):source.find("function sortBy(")]
        matches = source[source.find("function sectionMatches("):source.find("function applySectionFilters(")]
        self.assertIn("compareSort(a, b, key, direction)", source[source.find("function sortBy("):source.find("function syncCardOrder(")])
        self.assertIn("compareSort(a, b, key, direction)", source[source.find("function sortSection("):source.find("function sectionMatches(")])
        script = """
function brandSame(a, b) {
  return String(a || "").toLowerCase() === String(b || "").toLowerCase();
}
let state = {search: "", store: "all", part: "all", brand: "all", priceMin: null, priceMax: null, widths: ["8.5"]};
""" + compare + matches + """
function row(data) { return {dataset: data}; }
const rows = [
  row({price: "40.00", store: "Zumiez", part: "Decks", brand: "Baker", search: "Baker deck"}),
  row({price: "12.50", store: "CCS", part: "Wheels", brand: "Spitfire", search: "Spitfire wheel"}),
  row({price: "", store: "Tactics", part: "Trucks", brand: "Independent", search: "Independent truck"}),
  row({price: "19.00", store: "Zumiez", part: "Decks", brand: "Chocolate", search: "Chocolate deck"}),
];
function prices(list) { return list.map(item => item.dataset.price).join(","); }
const asc = rows.slice().sort((a, b) => compareSort(a, b, "price", "asc"));
if (prices(asc) !== "12.50,19.00,40.00,") throw new Error("asc " + prices(asc));
const desc = rows.slice().sort((a, b) => compareSort(a, b, "price", "desc"));
if (prices(desc) !== "40.00,19.00,12.50,") throw new Error("desc " + prices(desc));
state.store = "Zumiez";
if (rows.filter(sectionMatches).length !== 2) throw new Error("store");
state.store = "all";
state.part = "Wheels";
if (rows.filter(sectionMatches).map(item => item.dataset.part).join() !== "Wheels") throw new Error("part");
state.part = "all";
state.brand = "baker";
if (rows.filter(sectionMatches).length !== 1) throw new Error("brand");
state.brand = "all";
state.search = "spit";
if (rows.filter(sectionMatches).length !== 1) throw new Error("search");
state.search = "";
state.priceMax = 20;
if (prices(rows.filter(sectionMatches)) !== "12.50,19.00") throw new Error("price");
if (state.widths[0] !== "8.5") throw new Error("width must not be part of this filter");
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cards_follow_every_sort_including_percent_off(self):
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        index = source[source.find("function indexDeals("):source.find("function readJson(")]
        sort = source[source.find("const SORT_NUMERIC"):source.find("function sortTable(")]
        self.assertIn('tbody.querySelectorAll(".deal-row")', sort)
        self.assertNotIn("dealRows().forEach", sort[sort.find("function syncCardOrder("):])
        self.assertIn('sortBy("discount", "desc")', source[source.find("function applySortChoice("):source.find("function toggleSection(")])
        script = r"""
let state = { sortKey: "rank", sortDir: "asc" };
let rowList = null;
let rowById = null;
let cardById = null;
let detailById = null;
function mirrorSort() {}
function syncUrl() {}
""" + index + sort + r"""
function el(tag, opts) {
  opts = opts || {};
  const node = {
    tag: tag,
    id: opts.id || "",
    className: opts.className || "",
    dataset: Object.assign({}, opts.dataset),
    attrs: Object.assign({}, opts.attrs),
    children: [],
    parent: null
  };
  node.classList = {
    contains(name) { return node.className.split(/\s+/).indexOf(name) >= 0; },
    add(name) { if (!node.classList.contains(name)) node.className = (node.className + " " + name).trim(); },
    remove(name) { node.className = node.className.split(/\s+/).filter(part => part && part !== name).join(" "); }
  };
  node.appendChild = function(child) {
    if (child.parent) child.parent.children = child.parent.children.filter(item => item !== child);
    child.parent = node;
    node.children.push(child);
    return child;
  };
  node.querySelectorAll = function(selector) { return queryAll(node, selector); };
  node.querySelector = function(selector) { return queryAll(node, selector)[0] || null; };
  return node;
}
function compound(part) {
  const preds = [];
  let i = 0;
  while (i < part.length) {
    if (part[i] === "#") {
      const m = /^[\w-]+/.exec(part.slice(i + 1));
      preds.push(node => node.id === m[0]);
      i += 1 + m[0].length;
    } else if (part[i] === ".") {
      const m = /^[\w-]+/.exec(part.slice(i + 1));
      preds.push(node => node.classList.contains(m[0]));
      i += 1 + m[0].length;
    } else if (part[i] === "[") {
      const end = part.indexOf("]", i);
      const body = part.slice(i + 1, end);
      const eq = /^([\w-]+)="([^"]*)"$/.exec(body);
      if (eq) preds.push(node => (node.attrs[eq[1]] || "") === eq[2]);
      else preds.push(node => Object.prototype.hasOwnProperty.call(node.attrs, body));
      i = end + 1;
    } else {
      const m = /^[\w-]+/.exec(part.slice(i));
      preds.push(node => node.tag === m[0]);
      i += m[0].length;
    }
  }
  return node => preds.every(pred => pred(node));
}
function queryAll(root, selector) {
  const preds = selector.trim().split(/\s+/).map(compound);
  let nodes = [root];
  preds.forEach(pred => {
    const next = [];
    nodes.forEach(start => {
      const walk = node => {
        node.children.forEach(child => {
          if (pred(child)) next.push(child);
          walk(child);
        });
      };
      walk(start);
    });
    nodes = next;
  });
  return nodes;
}
const doc = el("doc");
doc.getElementById = id => queryAll(doc, "#" + id)[0] || null;
doc.querySelector = selector => queryAll(doc, selector)[0] || null;
doc.querySelectorAll = selector => queryAll(doc, selector);
global.document = doc;
const tbody = el("tbody");
const table = el("table", { id: "mainTable" });
table.appendChild(tbody);
const grid = el("div", { id: "cardGrid" });
const board = el("div", { id: "groupBoard" });
doc.appendChild(table);
doc.appendChild(grid);
doc.appendChild(board);
function addDeal(data) {
  const row = el("tr", { className: "deal-row", dataset: data, attrs: { "data-group": data.group || "" } });
  const card = el("article", { className: "deal-card", dataset: Object.assign({}, data) });
  tbody.appendChild(row);
  grid.appendChild(card);
  return { row, card };
}
// Rank order pins the new 12% decks first. % off must not.
addDeal({ id: "new", discount: "12.5", price: "92.75", original: "106.00", score: "40", rank: "0", size: "10.0", store: "CCS", brand: "Powell-Peralta", days: "1", daysat: "1", added: "1", group: "" });
addDeal({ id: "hot", discount: "51.7", price: "69.99", original: "144.95", score: "80", rank: "1", size: "13.5", store: "Zumiez", brand: "Heroin", days: "40", daysat: "9", added: "0", group: "g-hot" });
addDeal({ id: "mid", discount: "20.0", price: "79.95", original: "99.95", score: "55", rank: "2", size: "10.0", store: "Tactics", brand: "Welcome", days: "20", daysat: "4", added: "0", group: "g-mid" });
addDeal({ id: "low", discount: "", price: "30.00", original: "", score: "10", rank: "3", size: "", store: "SkateWarehouse", brand: "ATM", days: "5", daysat: "12", added: "0", group: "g-mid" });
addDeal({ id: "other", discount: "40.0", price: "50.00", original: "83.33", score: "70", rank: "4", size: "8.5", store: "CCS", brand: "Baker", days: "15", daysat: "2", added: "0", group: "g-hot" });
const groupHot = el("article", { className: "group-card", dataset: { key: "g-hot" } });
const groupMid = el("article", { className: "group-card", dataset: { key: "g-mid" } });
board.appendChild(groupMid);
board.appendChild(groupHot);
dealRows();
function ids(nodes) { return nodes.map(node => node.dataset.id).join(","); }
function groups() { return board.querySelectorAll(".group-card").map(node => node.dataset.key).join(","); }
function cards() { return grid.querySelectorAll(".deal-card"); }
function rows() { return tbody.querySelectorAll(".deal-row"); }
sortBy("discount", "desc");
if (ids(cards()) !== "hot,other,mid,new,low") throw new Error("discount cards " + ids(cards()));
if (ids(rows()) !== ids(cards())) throw new Error("discount rows " + ids(rows()));
if (groups() !== "g-hot,g-mid") throw new Error("discount groups " + groups());
const checks = [
  ["price", "asc", "low,other,hot,mid,new"],
  ["price", "desc", "new,mid,hot,other,low"],
  ["score", "desc", "hot,other,mid,new,low"],
  ["original", "asc", "other,mid,new,hot,low"],
  ["size", "asc", "other,mid,new,hot,low"],
  ["store", "asc", "other,new,low,mid,hot"],
  ["brand", "asc", "low,other,hot,new,mid"],
  ["days", "desc", "hot,mid,other,low,new"],
  ["daysat", "asc", "new,other,mid,hot,low"],
  ["rank", "asc", "new,hot,mid,low,other"]
];
checks.forEach(spec => {
  sortBy(spec[0], spec[1]);
  if (ids(cards()) !== spec[2]) throw new Error(spec[0] + " " + spec[1] + " cards " + ids(cards()));
  if (ids(rows()) !== ids(cards())) throw new Error(spec[0] + " rows diverged");
});
sortBy("discount", "desc");
rows().forEach(row => { if (row.dataset.id === "other") row.classList.add("filtered-out"); });
syncGroupOrder();
if (groups() !== "g-hot,g-mid") throw new Error("filtered group still led by 51.7 " + groups());
rows().forEach(row => { if (row.dataset.id === "hot") row.classList.add("filtered-out"); });
syncGroupOrder();
if (groups() !== "g-mid,g-hot") throw new Error("group follows the deals still showing " + groups());
const visible = cards().filter(card => card.dataset.id !== "hot" && card.dataset.id !== "other").map(card => card.dataset.discount);
if (visible.join(",") !== "20.0,12.5,") throw new Error("visible discounts " + visible.join(","));
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_desktop_shell_fits_under_the_nav(self):
        html = build_report_html(
            {"Zumiez_Decks": [_deck("40.00", "https://example.com/d", "Zumiez", "Baker Team Deck 8.0")]},
            {},
            generated_at="2026-10-15T12:00:00+00:00",
        )
        style = html.split("<style>", 1)[1].split("</style>", 1)[0]
        base = style.split("@media (min-width: 801px)", 1)[0]
        self.assertIn("min-height: 100vh;", base)
        desktop = style.split("@media (min-width: 801px)", 1)[1].split("@media", 1)[0]
        shell = desktop.split(".shell", 1)[1].split("}", 1)[0]
        self.assertIn("height: calc(100vh - var(--stick-top, 92px));", shell)
        self.assertIn("min-height: 0;", shell)
        self.assertIn("overflow: hidden;", shell)

    def test_desktop_table_header_sticks_under_the_nav(self):
        html = build_report_html(
            {"Zumiez_Decks": [_deck("40.00", "https://example.com/d", "Zumiez", "Baker Team Deck 8.0")]},
            {},
            generated_at="2026-10-15T12:00:00+00:00",
        )
        style = html.split("<style>", 1)[1].split("</style>", 1)[0]
        base = style.split("@media (min-width: 801px)", 1)[0]
        self.assertIn("top: var(--stick-top);", base)
        desktop = style.split("@media (min-width: 801px)", 1)[1].split("@media", 1)[0]
        self.assertIn("thead th { top: -0.4rem; }", desktop)
        self.assertIn(".diagnostics thead th", style)
        self.assertIn("position: static;", style.split(".diagnostics thead th", 1)[1].split("}", 1)[0])

    def test_logo_and_clear_all_return_to_the_default_view(self):
        html = build_report_html(
            {"Zumiez_Decks": [_deck("40.00", "https://example.com/d", "Zumiez", "Baker Team Deck 8.0")]},
            {},
            generated_at="2026-10-15T12:00:00+00:00",
        )
        self.assertIn('id="homeReset"', html)
        self.assertIn('title="Back to default view"', html)
        self.assertIn('class="brand-home"', html)
        self.assertEqual(html.count('onclick="clearFilters()"'), 2)
        style = html.split("<style>", 1)[1].split("</style>", 1)[0]
        home = style.split(".brand-home", 1)[1].split("}", 1)[0]
        self.assertIn("cursor: pointer;", home)
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        reset = source[source.find("function clearFilters("):source.find("function scrollResultsToTop(")]
        self.assertNotIn("visitMode", reset)
        self.assertIn("grouped: false", reset)
        self.assertIn('part: "Decks"', reset)
        self.assertIn("sortKey: DEFAULT_SORT", reset)
        self.assertIn('sortBy(DEFAULT_SORT, "desc")', reset)
        self.assertIn("scrollResultsToTop()", reset)
        self.assertNotIn("applyLayout(", reset)
        self.assertNotIn("LAYOUT_KEY", reset)
        history = source[source.find("const SEARCH_HISTORY_MS"):source.find("function applySnapshot(")]
        self.assertIn("SEARCH_HISTORY_MS", source)
        self.assertIn('window.addEventListener("popstate", restoreFromUrl)', source)
        script = history + r"""
if (historyAction(null, "") !== "replace") throw new Error("first load");
if (historyAction("", "") !== "none") throw new Error("same");
if (historyAction("", "sort=discount") !== "push") throw new Error("sort");
if (historyAction("sort=discount", "sort=price") !== "push") throw new Error("sort change");
if (historyAction("", "type=wheel") !== "push") throw new Error("type");
if (historyAction("type=wheel", "store=zumiez&type=wheel") !== "push") throw new Error("store");
if (historyAction("", "change=new") !== "push") throw new Error("deal tab");
if (historyAction("change=new", "change=drop") !== "push") throw new Error("deal tab change");
if (historyAction("sort=discount&type=wheel", "") !== "push") throw new Error("reset");
if (historyAction("", "q=b") !== "search") throw new Error("first letter");
if (historyAction("q=b", "q=ba") !== "search") throw new Error("next letter");
if (historyAction("q=baker", "q=baker&sort=discount") !== "push") throw new Error("search plus sort");
if (historyAction("sort=discount", "q=a&sort=discount") !== "search") throw new Error("search on a sorted view");
if (SEARCH_HISTORY_MS < 200) throw new Error("search history is not debounced");
let last = "";
let pushes = 0;
function step(next, commitSearch) {
  const action = historyAction(last, next);
  if (action === "none") return action;
  if (action === "search" && !commitSearch) return "wait";
  if (action !== "replace") pushes += 1;
  last = next;
  return action;
}
if (step("type=wheel", true) !== "push") throw new Error("type step");
if (step("q=b&type=wheel", false) !== "wait") throw new Error("letter");
if (step("q=ba&type=wheel", false) !== "wait") throw new Error("letters");
if (step("q=baker&type=wheel", true) !== "search") throw new Error("commit");
if (pushes !== 2) throw new Error("search burst pushed " + pushes);
last = "";
pushes = 0;
step("q=b", false);
step("q=baker", true);
if (pushes !== 1) throw new Error("default search pushed " + pushes);
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


    def test_card_quick_view_replaces_title_tooltips(self):
        deck = _deck(
            "49.99",
            "https://example.com/deck",
            "Zumiez",
            'Baker Kevin Spanky Deck 8.25"',
        )
        shoe = {
            "name": "Vans Skate Old Skool Wafflecup Shoes - Willow Green/Black",
            "url": "https://example.com/shoe",
            "price_new": "59.50",
            "price_old": "85.00",
            "part": "Sneakers",
            "store": "CCS",
            "shoe_sizes": ["7.5", "8"],
        }
        html = build_report_html(
            {"Zumiez_Decks": [deck], "CCS_Sneakers": [shoe]},
            {},
            generated_at="2026-10-17T20:22:15+00:00",
        )
        self.assertNotIn('class="title-pop"', html)
        self.assertNotIn('class="card-hover"', html)
        self.assertNotIn(".title-slot:hover .title-pop", html)
        self.assertIn('id="quickView"', html)
        self.assertIn("const QUICK_OPEN_MS = 300;", html)
        cards = [
            part.split("</article>", 1)[0]
            for part in html.split('<article class="deal-card')[1:]
        ]
        self.assertGreaterEqual(len(cards), 2)
        for card in cards:
            self.assertIn('<h3 class="product-name">', card)
            self.assertNotIn('class="product-name" title=', card)
            self.assertNotIn(">Details</button>", card)
            self.assertIn('class="card-quick"', card)
            self.assertIn('class="card-score" hidden', card)
        shoe_card = next(card for card in cards if "Willow Green" in card)
        self.assertIn('data-shoesize="7.5,8"', shoe_card)
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        refresh = source[source.find("function refreshCharts("):source.find("function clipSeries(")]
        self.assertNotIn("drawQuickChart", refresh)
        self.assertNotIn("fillQuickView", refresh)
        self.assertIn("closeProduct();\n            closeQuickView();", source)
        add_days = source[source.find("function addDays("):source.find("function markerColor(")]
        facts = source[source.find("function quickClip("):source.find("function quickGalleryImages(")]
        script = "const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];\n" + add_days + facts + r"""
const shoe = quickFacts(
  {price: "59.50", original: "85", discount: "30", days: "18", daysat: "4", shoesize: "7.5,8", size: "", length: "", wheelbase: "", diameter: "", duros: "", shape: "", trucksize: "", truckheight: "", construction: "", abec: "", store: "CCS"},
  {
    url: "https://example.com/shoe",
    store: "CCS",
    first: "2026-09-01",
    daily: [["2026-07-18", 90], ["2026-09-01", 70], ["2026-10-17", 59.5]],
    seriesList: [{url: "https://example.com/shoe", low: {date: "2026-10-01", price: 55}, points: [], markers: [
      {date: "2026-07-01", kind: "drop", price: 80, label: "old"},
      {date: "2026-10-17", kind: "drop", price: 59.5, label: "Price reduction −$10.50"}
    ]}],
    offers: [
      {store: "CCS", url: "https://example.com/shoe", price: 59.5, currency: "USD", cheapest: false},
      {store: "Tactics", url: "https://example.com/tactics", price: 64, currency: "USD", cheapest: false}
    ]
  },
  "2026-10-17"
);
const labels = shoe.rows.map(row => row.label + "=" + row.value).join(" | ");
if (!labels.includes("List price=$85.00")) throw new Error(labels);
if (labels.includes("You save")) throw new Error(labels);
if (!labels.includes("Claimed discount=30% vs list")) throw new Error(labels);
if (!labels.includes("All-time low=$55.00 on Oct 1")) throw new Error(labels);
if (!labels.includes("90-day average=$64.75")) throw new Error(labels);
if (!labels.includes("First seen=Sep 1")) throw new Error(labels);
if (!labels.includes("Tracked=18 days")) throw new Error(labels);
if (!labels.includes("At this price=4 days")) throw new Error(labels);
if (shoe.points.some(point => point[0] === "2026-07-18")) throw new Error("old point stayed in the 90-day window");
if (shoe.specs.map(row => row.label + " " + row.value).join() !== "In stock 7.5, 8") throw new Error(JSON.stringify(shoe.specs));
if (shoe.stores.length !== 1 || shoe.stores[0].label !== "Tactics $64.00") throw new Error(JSON.stringify(shoe.stores));
if (shoe.viewLabel !== "View at CCS") throw new Error(shoe.viewLabel);
if (shoe.firstText !== "Sep 1") throw new Error(shoe.firstText);
if (shoe.markers.length !== 1 || shoe.markers[0].date !== "2026-10-17") throw new Error(JSON.stringify(shoe.markers));
const deck = quickFacts(
  {price: "49.99", original: "", discount: "", days: "0", daysat: "0", shoesize: "", size: "8.25", length: "31.875", wheelbase: "", diameter: "", duros: "", shape: "", trucksize: "", truckheight: "", construction: "", abec: ""},
  {url: "https://example.com/deck", store: "Zumiez", first: "", daily: [], seriesList: [], offers: [{store: "Zumiez", url: "https://example.com/deck", price: 49.99}]},
  "2026-10-17"
);
if (deck.rows.length) throw new Error("empty deck facts " + JSON.stringify(deck.rows));
if (deck.points.length) throw new Error("deck chart");
if (deck.stores.length) throw new Error("deck stores");
const specText = deck.specs.map(row => row.label + " " + row.value).join(" | ");
if (specText !== 'Width 8.25" | Length 31.875"') throw new Error(specText);
const wheel = quickFacts(
  {diameter: "54-55", duros: "99a,95a", shape: "Conical", shoesize: "", size: ""},
  {url: "https://example.com/wheel", offers: []},
  "2026-10-17"
);
if (wheel.specs.map(row => row.value).join() !== "54-55,99a, 95a,Conical") throw new Error(JSON.stringify(wheel.specs));
const same = quickFacts(
  {price: "40", original: "40", discount: "0", days: "1", daysat: "1"},
  {url: "https://example.com/same", store: "CCS", first: "2026-10-16", offers: [{url: "https://example.com/same", currency: "EUR", price: 40}]},
  "2026-10-17"
);
const sameText = same.rows.map(row => row.label + "=" + row.value).join(" | ");
if (!sameText.includes("List price=€40.00")) throw new Error(sameText);
if (sameText.includes("You save")) throw new Error(sameText);
if (sameText.includes("Off=")) throw new Error(sameText);
if (!sameText.includes("Tracked=1 day")) throw new Error(sameText);
if (sameText.includes("At this price")) throw new Error(sameText);
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
