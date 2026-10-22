"""Audience separation: SMTP is always mocked; no scrape or live delivery."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from notify import send_admin_warnings, send_digest, write_preview
from report import Digest, build_report_html
from test_notify import _deck, _full_env

WARNING = {
    "store": "Zumiez", "part": "Decks", "key": "Zumiez_Decks", "kind": "incomplete",
    "expected_count": 100, "actual_count": 20, "percentage_change": -80,
    "reason": "catalog_drop", "dates": ["2026-10-22"],
}


class AudienceTests(unittest.TestCase):
    def test_public_page_has_no_health_panel_failure_keys_or_expected_counts(self):
        digest = Digest(new_items=[_deck()], warnings=[WARNING])
        html = build_report_html({"Zumiez_Decks": [_deck()]}, {}, {},
                                 failed_keys=["PRIVATE_CATEGORY"], digest=digest)
        for text in ('id="diagnostics"', 'id="diagToggle"', 'PRIVATE_CATEGORY',
                     'expected about', 'Scan failed for', 'Store check failed',
                     'warn-badge">Warning', '"failed":'):
            self.assertNotIn(text, html, msg=text)
        self.assertIn(_deck()["url"], html)

    def test_deal_and_admin_messages_have_separate_recipients_and_content(self):
        env = dict(_full_env(), EMAIL_TO="subscriber@example.com", ADMIN_EMAIL_TO="admin@example.com")
        with patch("notify._smtp_send", return_value={}) as send:
            self.assertTrue(send_digest(Digest(new_items=[_deck()], warnings=[WARNING]), env=env))
            self.assertTrue(send_admin_warnings([WARNING], env=env))
        self.assertEqual(send.call_count, 2)
        deal, admin = [call.args[1] for call in send.call_args_list]
        self.assertEqual(str(deal['To']), 'subscriber@example.com')
        self.assertEqual(str(admin['To']), 'admin@example.com')
        self.assertNotIn('admin@example.com', deal.as_string())
        for text in ('scraper warning', 'expected about', 'catalog_drop'):
            self.assertNotIn(text, deal.as_string())
        plain = admin.get_content()
        self.assertIn('Zumiez Decks', plain)
        self.assertIn('100', plain)
        self.assertIn('20', plain)
        self.assertIn('-80', plain)
        self.assertIn('retry', plain)
        self.assertIn('[SkateDeals ADMIN]', admin['Subject'])

    def test_admin_never_falls_back_to_subscribers(self):
        with patch('notify._smtp_send') as send:
            self.assertFalse(send_admin_warnings([WARNING], env=_full_env()))
        send.assert_not_called()

    def test_admin_dry_run_and_recovery_send_nothing(self):
        env = dict(_full_env(), ADMIN_EMAIL_TO='admin@example.com')
        with patch('notify._smtp_send') as send, patch('notify.write_preview') as preview:
            self.assertFalse(send_admin_warnings([WARNING], env=env, dry_run=True))
            self.assertFalse(send_admin_warnings([WARNING], env=dict(env, EMAIL_DRY_RUN='1')))
            self.assertFalse(send_admin_warnings([], env=env))
        send.assert_not_called()
        preview.assert_not_called()

    def test_smtp_error_does_not_leak_addresses_or_prevent_deal_delivery(self):
        env = dict(_full_env(), ADMIN_EMAIL_TO='admin@example.com')
        with patch('notify._smtp_send', side_effect=RuntimeError('admin@example.com password')):
            with self.assertLogs('notify', level='WARNING') as logs:
                self.assertFalse(send_admin_warnings([WARNING], env=env))
        self.assertNotIn('admin@example.com', '\n'.join(logs.output))
        self.assertNotIn('password', '\n'.join(logs.output))
        with patch('notify._smtp_send', return_value={}):
            self.assertTrue(send_digest(Digest(new_items=[_deck()]), env=env))

    def test_preview_does_not_embed_addresses_even_in_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'preview.html'
            write_preview(path, 'SkateDeals', '<p>A deal</p>', ['subscriber@example.com'])
            self.assertNotIn('subscriber@example.com', path.read_text())

    def test_pages_excludes_every_internal_root_and_runtime_output(self):
        excluded = {json.loads(line[4:]) for line in Path('_config.yml').read_text().splitlines() if line.startswith('  - ')}
        self.assertFalse(Path('.nojekyll').exists(), 'Pages must honor Jekyll exclusions')
        public = {'_config.yml', 'sale_items_chart.html', 'page.css', 'mobile.css', 'page.js'}
        roots = {path.split('/')[0] for path in subprocess.check_output(['git','ls-files'], text=True).splitlines()}
        self.assertEqual(roots - excluded - public, set())
        for path in ('scrape_health.json', 'previous_data.json', 'price_history.json',
                     'site_sales.json', 'email_preview.html', 'notification_state.json', 'worker',
                     'watchlist.yaml', 'alerts_state', 'docs', 'audit'):
            self.assertIn(path, excluded)

    def test_checked_in_page_is_clean_including_embedded_data(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(Path('sale_items_chart.html').read_text(), 'html.parser')
        self.assertFalse(soup.select('#diagnostics, #diagToggle, .warn-badge, header.is-failed, header.is-stale'))
        payload = json.loads(soup.select_one('#catalogJson').string)
        self.assertNotIn('failed', payload)
        self.assertNotIn('warnings', payload)
        self.assertNotIn('diagnostics', payload)
        self.assertTrue(payload['items'])

    def test_invalid_admin_configuration_is_isolated(self):
        with patch('notify._smtp_send') as send:
            self.assertFalse(send_admin_warnings([WARNING], env={'ADMIN_EMAIL_TO': 'admin@example.com'}))
            self.assertFalse(send_admin_warnings([{'kind': 'incomplete'}], env=_full_env()))
        send.assert_not_called()

    def test_workflow_wires_separate_admin_secret(self):
        workflow = Path('.github/workflows/scrape.yml').read_text()
        self.assertIn('ADMIN_EMAIL_TO: ${{ secrets.ADMIN_EMAIL_TO }}', workflow)
        self.assertIn('git add sale_items_chart.html previous_data.json price_history.json scrape_health.json', workflow)


if __name__ == '__main__':
    unittest.main()
