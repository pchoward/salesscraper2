"""Live Catalog is opt-in and separate from saved first-party catalog state."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import page
from previews.publish import publish
from report import build_report_html

ROOT = Path(__file__).parent


class CatalogSearchTests(unittest.TestCase):
    def test_default_off_and_section_after_our_results(self):
        html = build_report_html({}, {}, generated_at='2026-11-12T00:00:00+00:00')
        self.assertIn('id="liveCatalogSettings">{"enabled": false, "apiBase": ""}', html)
        self.assertIn('id="liveCatalogDeals" class="catalog-live" aria-labelledby="liveCatalogTitle" hidden', html)
        self.assertLess(html.index('id="cardGrid"'), html.index('id="liveCatalogDeals"'))
        self.assertIn('root.ShredCatalogSearch = api', html)
        self.assertFalse(page.LIVE_CATALOG_UI_CONFIG['enabled'])

    def test_public_configuration_is_safe_json(self):
        with patch.object(page, 'LIVE_CATALOG_UI_CONFIG', {'enabled': True, 'apiBase': '</script><script>bad</script>'}):
            html = build_report_html({}, {}, generated_at='2026-11-12T00:00:00+00:00')
        config = html.split('id="liveCatalogSettings">', 1)[1].split('</script>', 1)[0]
        self.assertNotIn('<', config)
        self.assertEqual(json.loads(config)['apiBase'], '</script><script>bad</script>')

    def test_money_uses_iso_minor_units(self):
        script = """
const assert=require('node:assert/strict'),{formatMoney}=require('./catalog-search.js');
assert.equal(formatMoney({amount:8999,currency:'USD'}),'$89.99');
assert.equal(formatMoney({amount:950,currency:'JPY'}),'¥950');
assert.match(formatMoney({amount:1500,currency:'BHD'}),/1\\.500/);
assert.equal(formatMoney({amount:0,currency:'USD'}),'$0.00');
assert.equal(formatMoney({amount:1.2,currency:'USD'}),'');
"""
        result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_profile_is_published_without_checkout_or_promoted_capabilities(self):
        profile = json.loads((ROOT / '.well-known/ucp-agent.json').read_text())
        self.assertEqual(set(profile['ucp']['capabilities']), {
            'dev.ucp.shopping.catalog.search', 'dev.ucp.shopping.catalog.lookup', 'dev.shopify.catalog.global'})
        self.assertEqual(profile['ucp']['payment_handlers'], {})
        self.assertEqual(profile['ucp']['services']['dev.ucp.shopping'][0]['endpoint'], 'https://catalog.shopify.com/api/ucp/mcp')
        with tempfile.TemporaryDirectory() as directory:
            publish(Path(directory))
            self.assertEqual(json.loads((Path(directory)/'.well-known/ucp-agent.json').read_text()), profile)
        config = (ROOT/'_config.yml').read_text()
        self.assertIn('include:\n  - ".well-known"', config)
