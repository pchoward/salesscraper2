"""Synthetic access-policy fixtures, not evidence of retailer stock or approval."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

from audit.bmx_readiness import CANDIDATES, SOURCE, fetch, research, run


class BmxReadinessTests(unittest.TestCase):
    def test_proxy_denial_never_requests_pages_or_claims_empty_catalog(self):
        get = Mock(return_value={'status': 'environment_proxy_denied', 'body': ''})
        result, evidence = research(CANDIDATES[0], get, lambda _: None)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(result['status'], 'access_unverified')
        self.assertIsNone(result['products_observed'])
        self.assertFalse(result['catalog_scan'])
        self.assertFalse(result['approved_source'])
        self.assertEqual(evidence, {})

    def test_robots_unavailable_or_denied_never_fetches_products(self):
        for status, body in [(404, ''), (503, ''), (200, 'User-agent: *\nDisallow: /')]:
            with self.subTest(status=status, body=body):
                get = Mock(return_value={'status': status, 'body': body})
                result, _ = research(CANDIDATES[0], get, lambda _: None)
                self.assertEqual(get.call_count, 1)
                self.assertFalse(result['approved_source'])

    def test_capture_terms_and_platform_without_requesting_a_feed(self):
        get = Mock(side_effect=[
            {'status': 200, 'body': 'User-agent: *\nAllow: /\nCrawl-delay: 5'},
            {'status': 200, 'body': '<script>Shopify.theme={}</script><a href="/sale">Sale</a><a href="/policies/terms-of-service">Terms</a>'},
            {'status': 200, 'body': 'Review these terms before automation.'},
        ])
        pauses = []
        result, evidence = research(CANDIDATES[1], get, pauses.append)
        self.assertEqual(result['status'], 'terms_review_required')
        self.assertEqual(result['platform'], ['Shopify'])
        self.assertEqual(pauses, [5, 5])
        self.assertIn('terms-1.html', evidence)
        self.assertFalse(result['approved_source'])
        self.assertEqual(get.call_count, 3)
        self.assertNotIn('products.json', str(get.call_args_list))

    def test_foreign_and_disallowed_terms_are_not_fetched(self):
        get = Mock(side_effect=[
            {'status': 200, 'body': 'User-agent: *\nDisallow: /private\nAllow: /'},
            {'status': 200, 'body': '<a href="https://other.example/terms">Terms</a><a href="/private/terms">Terms</a>'},
        ])
        result, _ = research(CANDIDATES[0], get, lambda _: None)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(result['terms'][0]['status'], 'robots_disallowed')

    def test_output_is_isolated_and_records_unknown_counts(self):
        get = Mock(return_value={'status': 'environment_proxy_denied', 'body': ''})
        with tempfile.TemporaryDirectory() as directory:
            result = run(Path(directory)/'evidence', get, lambda _: None)
            self.assertFalse(result['production_scan'])
            self.assertTrue(all(r['products_observed'] is None for r in result['retailers']))
            self.assertTrue((Path(directory)/'evidence/readiness.json').is_file())
            with self.assertRaises(ValueError): run(Path(directory)/'evidence', get)
        with self.assertRaises(ValueError): run(SOURCE/'never-write-bmx-evidence', get)

    def test_transport_denial_is_not_reported_as_retailer_http_403(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=urllib.error.URLError('Tunnel connection failed: 403 Forbidden')):
            self.assertEqual(fetch('https://www.sourcebmx.com/robots.txt')['status'], 'environment_proxy_denied')


if __name__ == '__main__':
    unittest.main()
