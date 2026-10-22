"""Development tools cannot publish state or deliver mail. All scrapes are mocked."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import smtplib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import devtools as dev
from test_notify import _deck


@contextlib.contextmanager
def working_directory(path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


class DevToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        self.stamp = '2026-09-28T10:15:00+00:00'
        objects = {
            'previous_data.json': {'Zumiez_Decks': [_deck()], 'Tactics_Decks': [_deck()]},
            'price_history.json': {},
            'scrape_health.json': {'runs': [{'date': '2026-09-28', 'scanned_at': self.stamp,
                                           'results': {'Zumiez_Decks': {'count': 1, 'failed': False}}}], 'baseline': {}},
            'site_sales.json': {},
            'notification_state.json': {'private': 'must remain unchanged'},
            'notification_state.json.lock': {},
        }
        for name, value in objects.items():
            (self.source/name).write_text(json.dumps(value))
        for name in ('tracked.yaml', 'watchlist.yaml'):
            (self.source/name).write_bytes((dev.SOURCE/name).read_bytes())
        (self.source/'sale_items_chart.html').write_text('production HTML')
        self.before = self.hashes(self.source)

    def hashes(self, path):
        return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in path.rglob('*') if p.is_file()}

    def workspace(self):
        return dev.prepare_workspace(self.source, self.base/'run')

    def worker(self, root, *args, **kwargs):
        with working_directory(root), patch.dict(os.environ, dev.sanitized_env(root), clear=True):
            return dev.run_worker(root, *args, **kwargs)

    def assert_isolated(self, root):
        self.assertEqual(self.before, self.hashes(self.source))
        manifest = json.loads((root/'manifest.json').read_text())
        self.assertFalse(manifest['complete_production_scan'])
        for name, digest in manifest['input_hashes'].items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(), digest)
        self.assertFalse((root/'notification_state.json').exists())

    def test_rebuild_cli_with_credentials_is_offline_and_preserves_timestamp(self):
        output = self.base/'preview'
        env = dict(os.environ, SMTP_HOST='smtp.invalid', SMTP_USER='test', SMTP_PASSWORD='secret',
                   EMAIL_TO='subscriber@example.com', ADMIN_EMAIL_TO='admin@example.com',
                   EMAIL_DRY_RUN='0', NOTIFICATION_ENGINE_ENABLED='1', ALERTS_DELIVERY_ENABLED='1')
        result = subprocess.run([sys.executable, '-m', 'devtools', 'rebuild', '--source-dir', str(self.source),
                                 '--output-dir', str(output)], cwd=dev.SOURCE, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'Preview HTML: {output}/preview.html', result.stdout)
        html = (output/'preview.html').read_text()
        self.assertIn('REBUILD ONLY', html)
        self.assertIn(self.stamp, html)
        self.assertIn('Content-Security-Policy', html)
        self.assertIn('connect-src &apos;none&apos;', html)
        self.assertNotIn('subscriber@example.com', html)
        self.assertNotIn('admin@example.com', html)
        self.assertEqual(json.loads((output/'manifest.json').read_text())['metrics'],
                         {'http_requests': 0, 'browser_starts': 0, 'browser_navigations': 0})
        self.assert_isolated(output)

    def test_rebuild_never_calls_network_browser_bookkeeping_or_notifications(self):
        root = self.workspace()
        with contextlib.ExitStack() as stack:
            calls = [stack.enter_context(patch(name, side_effect=AssertionError(name))) for name in (
                'urllib.request.urlopen', 'stores.browser.webdriver.Chrome', 'stores.runner.run_stores',
                'pipeline.apply_run_updates', 'history.record_misses', 'stores.stock.confirm_stock',
                'notify.send_digest', 'notify.send_admin_warnings', 'notification_engine.send_notifications',
                'alerts_delivery.deliver_subscriber_alerts')]
            self.assertEqual(self.worker(root, 'rebuild'), 0)
        for call in calls:
            call.assert_not_called()
        self.assert_isolated(root)

    def test_targeted_scrape_runs_one_real_parser_and_does_not_advance_lifecycle(self):
        root = self.workspace()
        from stores.tactics import TacticsScraper
        from stores.zumiez import ZumiezScraper
        selected = TacticsScraper('Tactics', 'https://www.tactics.com/shoes/sale', 'Sneakers')
        unselected = ZumiezScraper('Zumiez', 'https://www.zumiez.com/', 'Decks')
        fixture = (dev.SOURCE/'tests/fixtures/tactics_sale_cards.html').read_text()
        with patch('stores.registry.build_scrapers', return_value=[selected, unselected]), \
             patch('stores.tactics.collect_sale_pages', return_value=[fixture]) as fetch, \
             patch.object(unselected, 'scrape') as other, \
             patch('history.record_misses') as misses, patch('pipeline.apply_run_updates') as updates, \
             patch('stores.stock.confirm_stock') as stock, patch('notify.send_digest') as email, \
             patch('notification_engine.send_notifications') as notifications, \
             patch('alerts_delivery.deliver_subscriber_alerts') as alerts:
            self.assertEqual(self.worker(root, 'scrape', retailer='Tactics', category='Sneakers'), 0)
        fetch.assert_called_once()
        for call in (other, misses, updates, stock, email, notifications, alerts):
            call.assert_not_called()
        result = json.loads((root/'targeted-result.json').read_text())
        self.assertTrue(result['items'])
        self.assertFalse(result['complete_production_scan'])
        self.assertIn('PARTIAL', (root/'preview.html').read_text())
        self.assertEqual(result['saved_scan_timestamp'], self.stamp)
        self.assertTrue((root/'tactics_debug_sneakers.html').exists())
        self.assert_isolated(root)

    def test_brand_postfilter_is_explicit_and_cannot_remove_other_brands_from_history(self):
        root = self.workspace()
        scraper = Mock(name='scraper')
        scraper.name, scraper.part, scraper.candidates = 'Tactics', 'Sneakers', 2
        scraper.scrape.return_value = [{'name': 'Vans PopCush', 'store': 'Tactics', 'part': 'Sneakers'},
                                       {'name': 'Nike SB Dunk', 'store': 'Tactics', 'part': 'Sneakers'}]
        with patch('stores.registry.build_scrapers', return_value=[scraper]):
            self.assertEqual(self.worker(root, 'scrape', retailer='Tactics', category='Sneakers', brand='Vans'), 0)
        result = json.loads((root/'targeted-result.json').read_text())
        self.assertEqual([item['name'] for item in result['items']], ['Vans PopCush'])
        self.assertIn('post-filter only', result['brand_strategy'])
        self.assertEqual(result['diagnostics']['raw_kept_count'], 2)
        self.assert_isolated(root)

    def test_zumiez_brand_query_reuses_validated_selection_without_broad_fallback(self):
        from stores.zumiez import ZumiezSneakersScraper, brand_sale_url
        scraper = ZumiezSneakersScraper()
        robots = (dev.SOURCE/'tests/fixtures/zumiez_robots.txt').read_text()
        with patch('stores.zumiez.fetch_zumiez_robots', return_value=robots), \
             patch('stores.zumiez.ZumiezMultiScraper.scrape', return_value=[]) as fetch:
            self.assertIn('brand-query', dev.configure_brand(scraper, 'Vans'))
            scraper.scrape()
        fetch.assert_called_once()
        self.assertEqual(scraper.urls, [brand_sale_url('Vans')])

    def test_disallowed_zumiez_brand_produces_failed_partial_preview_without_fetch(self):
        from stores.zumiez import ZumiezSneakersScraper
        root = self.workspace()
        scraper = ZumiezSneakersScraper()
        with patch('stores.registry.build_scrapers', return_value=[scraper]), \
             patch('stores.zumiez.fetch_zumiez_robots', return_value=''), \
             patch('stores.zumiez.fetch_page') as fetch:
            self.assertEqual(self.worker(root, 'scrape', retailer='Zumiez', category='Sneakers', brand='Vans'), 1)
        fetch.assert_not_called()
        result = json.loads((root/'targeted-result.json').read_text())
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['complete_production_scan'])
        self.assertIn('FETCH FAILED', (root/'preview.html').read_text())
        self.assert_isolated(root)

    def test_empty_and_failed_targeted_results_never_become_full_scans(self):
        for value in ([], None):
            with self.subTest(value=value):
                root = dev.prepare_workspace(self.source, self.base/f'run-{value is None}')
                scraper = Mock()
                scraper.name, scraper.part, scraper.candidates = 'Tactics', 'Decks', 0
                scraper.scrape.return_value = value
                with patch('stores.registry.build_scrapers', return_value=[scraper]):
                    code = self.worker(root, 'scrape', retailer='Tactics', category='Decks')
                self.assertEqual(code, 0 if value == [] else 1)
                self.assert_isolated(root)

    def test_unsafe_output_existing_path_and_symlinks_are_rejected(self):
        for output in (self.source, self.source/'new-output', dev.SOURCE/'dev-output'):
            with self.subTest(output=output), self.assertRaises(ValueError):
                dev.prepare_workspace(self.source, output)
        link = self.base/'link'
        link.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError):
            dev.prepare_workspace(self.source, link)
        self.assertEqual(self.before, self.hashes(self.source))

    def test_worker_rejects_symlink_output_and_modified_inputs(self):
        root = self.workspace()
        (root/'preview.html').symlink_to(self.source/'sale_items_chart.html')
        with self.assertRaises(ValueError):
            self.worker(root, 'rebuild')
        (root/'preview.html').unlink()
        (root/'price_history.json').chmod(0o644)
        (root/'price_history.json').write_text('{}\n')
        with self.assertRaises(ValueError):
            self.worker(root, 'rebuild')
        self.assertEqual(self.before, self.hashes(self.source))

    def test_request_metrics_count_only_application_operations(self):
        import urllib.request
        from stores import browser
        metrics = dict(http_requests=0, browser_starts=0, browser_navigations=0)
        driver = Mock()
        with patch.object(urllib.request, 'urlopen') as http, \
             patch.object(browser.webdriver, 'Chrome', return_value=driver):
            with dev.request_metrics(metrics):
                urllib.request.urlopen('https://example.invalid')
                browser.webdriver.Chrome().get('https://example.invalid')
        http.assert_called_once()
        self.assertEqual(metrics, dict(http_requests=1, browser_starts=1, browser_navigations=1))

    def test_targeted_preview_excludes_history_for_omitted_products(self):
        (self.source/'price_history.json').write_text(json.dumps({
            'https://example.com/omitted': {'store': 'CCS', 'part': 'Decks',
                                            'stage': 'gone', 'miss_streak': 2}}))
        self.before = self.hashes(self.source)
        root = self.workspace()
        scraper = Mock()
        scraper.name, scraper.part, scraper.candidates = 'Tactics', 'Decks', 0
        scraper.scrape.return_value = []
        with patch('stores.registry.build_scrapers', return_value=[scraper]), \
             patch('devtools.render_preview', return_value='<html>partial</html>') as render:
            self.assertEqual(self.worker(root, 'scrape', retailer='Tactics', category='Decks'), 0)
        self.assertEqual(render.call_args.args[0], {'Tactics_Decks': []})
        self.assertEqual(render.call_args.args[1], {})
        self.assert_isolated(root)

    def test_timestamp_is_never_fabricated_when_historical_date_only(self):
        self.assertEqual(dev.scan_timestamp({'runs': [{'date': '2026-09-01'}]}), '2026-09-01')
        with self.assertRaises(ValueError):
            dev.scan_timestamp({'runs': []})

    def test_delivery_and_rebuild_network_guards_fail_closed(self):
        with dev.safety_guards(rebuild=True):
            with self.assertRaises(RuntimeError):
                smtplib.SMTP('example.invalid')
            with self.assertRaises(RuntimeError):
                smtplib.SMTP_SSL('example.invalid')
            with self.assertRaises(RuntimeError):
                __import__('urllib.request', fromlist=['urlopen']).urlopen('https://example.invalid')
        with dev.safety_guards(rebuild=False):
            with self.assertRaises(RuntimeError):
                smtplib.SMTP('example.invalid')
        with patch.dict(os.environ, {'SMTP_PASSWORD': 'secret', 'EMAIL_TO': 'private@example.com',
                                     'NOTIFICATION_ENGINE_ENABLED': '1', 'ALERTS_HMAC_SECRET': 'secret'}):
            env = dev.sanitized_env(self.base)
        self.assertNotIn('SMTP_PASSWORD', env)
        self.assertNotIn('EMAIL_TO', env)
        self.assertNotIn('ALERTS_HMAC_SECRET', env)
        self.assertEqual(env['NOTIFICATION_ENGINE_ENABLED'], '0')


if __name__ == '__main__':
    unittest.main()
