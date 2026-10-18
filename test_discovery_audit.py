"""Offline discovery evidence tests; no retailer requests or scrape-side writes."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from audit.discovery import audit, inspect_evidence, inventory, main
from stores import ccs

FIXTURES = Path(__file__).parent / 'tests' / 'fixtures' / 'discovery_audit'


class DiscoveryAuditTests(unittest.TestCase):
    def test_inventory_tracks_current_four_retailers_and_pagination(self):
        rows = inventory()
        self.assertEqual(len(rows), 24)
        keyed = {(r['store'], r['category']): r for r in rows}
        self.assertEqual({r['store'] for r in rows}, {'Zumiez', 'CCS', 'Tactics', 'SkateWarehouse'})
        self.assertEqual(keyed['CCS', 'Decks']['max_pages_per_entry'], 1)
        self.assertEqual(keyed['CCS', 'Sneakers']['page_size'], 250)
        self.assertIn('fails the feed', keyed['CCS', 'Sneakers']['limit_behavior'])
        self.assertIn('tracked.yaml', keyed['Zumiez', 'Sneakers']['runtime_note'])
        self.assertEqual(len(keyed['SkateWarehouse', 'Accessories']['entry_points']), 6)
        self.assertIn('no explicit incomplete', keyed['Tactics', 'Decks']['limit_behavior'])

    def test_fixture_manifest_compares_unique_candidates_without_claiming_valid_misses(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / 'catalog.json'
            catalog.write_text(json.dumps({'Tactics_Bearings': [{'url': 'https://www.tactics.com/bones-reds'}]}))
            original = catalog.read_bytes()
            report = audit(FIXTURES / 'manifest.json', catalog)
            self.assertEqual(catalog.read_bytes(), original)
        rows = {(r['store'], r['category']): r for r in report['observations']}
        bearings = rows['Tactics', 'Bearings']
        self.assertEqual(bearings['observed_unique_candidates'], 3)
        self.assertEqual(bearings['saved_filtered_count'], 1)
        self.assertEqual(bearings['candidates_not_in_saved_catalog'], ['https://www.tactics.com/bones-swiss', 'https://www.tactics.com/bronson-g3'])
        self.assertEqual(bearings['unprovided_pagination_urls'], ['https://www.tactics.com/skateboard-bearings/sale/page-3'])
        self.assertIsNone(rows['CCS', 'Bearings']['saved_filtered_count'])
        self.assertIsNone(rows['CCS', 'Bearings']['candidates_not_in_saved_catalog'])
        self.assertIn('not confirmed', report['limitations'][0])
        self.assertIn('Synthetic', report['evidence_label'])

    def test_json_feed_counts_products_not_variants_or_duplicate_handles(self):
        result = inspect_evidence((FIXTURES / 'ccs-feed.json').read_text(), 'json', 'https://shop.ccs.com/collections/clearance/products.json', 'CCS')
        self.assertEqual(len(result['product_urls']), 2)
        full = json.dumps({'products': [{'handle': f'p{i}'} for i in range(ccs.PAGE_LIMIT)]})
        self.assertIn('another page', inspect_evidence(full, 'json', 'https://shop.ccs.com/collections/clearance/products.json', 'CCS')['notes'][0])

    def test_sitemap_pages_indexes_and_images_are_not_sale_product_counts(self):
        result = inspect_evidence((FIXTURES / 'sitemap.xml').read_text(), 'sitemap', 'https://www.skatewarehouse.com/sitemap.xml', 'SkateWarehouse')
        self.assertEqual(len(result['sitemap_urls']), 2)
        self.assertEqual(result['product_urls'], [])
        self.assertFalse(any('photo' in u for u in result['sitemap_urls']))
        index = '<sitemapindex><sitemap><loc>https://shop.ccs.com/sitemap_products_1.xml</loc></sitemap></sitemapindex>'
        result = inspect_evidence(index, 'sitemap', 'https://shop.ccs.com/sitemap.xml', 'CCS')
        self.assertEqual(result['sitemap_indexes'], ['https://shop.ccs.com/sitemap_products_1.xml'])
        self.assertEqual(result['product_urls'], [])

    def test_embedded_structured_products_are_deduplicated(self):
        result = inspect_evidence((FIXTURES / 'structured.html').read_text(), 'html', 'https://www.tactics.com/skateboard-wheels/sale', 'Tactics')
        self.assertEqual(result['product_urls'], ['https://www.tactics.com/powell-wheels', 'https://www.tactics.com/spitfire-wheels'])
        ccs_html = '<article data-product=\'{"handle":"deck"}\'></article>'
        self.assertEqual(inspect_evidence(ccs_html, 'html', 'https://shop.ccs.com/collections/clearance', 'CCS')['product_urls'], ['https://shop.ccs.com/products/deck'])

    def test_shell_markup_and_bad_structured_data_are_inconclusive(self):
        body = '<a href="/search">search</a><script type="application/ld+json">broken</script>'
        result = inspect_evidence(body, 'html', 'https://www.tactics.com/skateboard-decks/sale', 'Tactics')
        self.assertEqual(result['product_urls'], [])
        self.assertTrue(any('shell/selector' in note for note in result['notes']))
        self.assertTrue(any('Unreadable JSON-LD' in note for note in result['notes']))

    def test_external_urls_and_unsafe_links_are_excluded(self):
        body = '<a class="ProductCard-Link" href="https://example.net/product">other</a><a class="ProductCard-Link" href="javascript:alert(1)">bad</a><a class="ProductCard-Link" href="/deck.html?utm_source=x#photo">deck</a>'
        result = inspect_evidence(body, 'html', 'https://www.zumiez.com/skate/sale', 'Zumiez')
        self.assertEqual(result['product_urls'], ['https://www.zumiez.com/deck.html'])
        with self.assertRaises(ValueError):
            inspect_evidence(body, 'html', 'https://example.net/sale', 'Zumiez')

    def test_no_network_scrape_parse_cache_or_debug_side_effects(self):
        old_cache = dict(ccs._CACHE)
        with patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')), \
             patch('stores.base.Scraper.scrape', side_effect=AssertionError('scrape forbidden')), \
             patch('stores.tactics.TacticsScraper.parse', side_effect=AssertionError('parser forbidden')), \
             patch('stores.browser.save_debug_file', side_effect=AssertionError('debug writes forbidden')):
            self.assertEqual(audit()['observations'], [])
            audit(FIXTURES / 'manifest.json')
        self.assertEqual(ccs._CACHE, old_cache)

    def test_cli_diagnostics_and_errors(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--manifest', str(FIXTURES / 'manifest.json'), '--format', 'json']), 0)
        self.assertEqual(json.loads(output.getvalue())['mode'], 'offline-read-only')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main(['--manifest', str(FIXTURES / 'manifest.json')])
        self.assertIn('not measured live inventory', output.getvalue())
        self.assertIn('Evidence:', output.getvalue())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(['--catalog', 'previous_data.json'])
        self.assertEqual(raised.exception.code, 2)
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / 'manifest.json'
            bad.write_text('{"version":1,"observations":[{"store":"Unknown","category":"Decks"}]}')
            with self.assertRaises(ValueError):
                audit(bad)
        with self.assertRaises(ValueError):
            inspect_evidence('{}', 'json', 'https://shop.ccs.com/collections/clearance/products.json', 'CCS')


if __name__ == '__main__':
    unittest.main()
