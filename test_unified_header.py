"""Native header contract, unchanged engine inputs, and inert preview output."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
from previews.shreddeals import HERE, SOURCE
from previews.unified_header import build, inject_header


class UnifiedHeaderTests(unittest.TestCase):
    def test_config_is_extensible_and_rejects_unsafe_or_ambiguous_links(self):
        script = r'''
const assert=require('assert'),H=require('./previews/unified-header.js');
const base='https://example.org/project/index.html';
const config={currentSport:'skate',sports:[{id:'skate',label:'Skate',href:'sale_items_chart.html'},{id:'bmx',label:'BMX',href:'bmx.html'}]};
assert.equal(H.validate(config,base),config);
config.sports.push({id:'surf',label:'Surf',href:'sports/surf.html'});
assert.equal(H.validate(config,base).sports.length,3);
assert.equal(H.pageURL(config.sports[2].href,base).pathname,'/project/sports/surf.html');
for(const href of ['https://evil.example/page','javascript:alert(1)','data:text/html,x','//evil.example/a','https://user:pass@example.org/a']) {
 assert.throws(()=>H.pageURL(href,base));
}
for(const bad of [[],[{id:'skate',label:'Skate',href:''}],config.sports.concat(config.sports[0])]) {
 assert.throws(()=>H.validate({...config,sports:bad},base));
}
assert.throws(()=>H.validate({...config,currentSport:'missing'},base));
assert.equal(H.nextIndex(0,'ArrowLeft',4),3);assert.equal(H.nextIndex(3,'ArrowRight',4),0);
assert.equal(H.nextIndex(2,'Home',4),0);assert.equal(H.nextIndex(0,'End',4),3);
assert.equal(H.nextIndex(0,'Tab',4),null);
'''
        result = subprocess.run(['node', '-e', script], cwd=SOURCE, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_native_preview_keeps_catalog_and_timestamps_without_modifying_sources(self):
        names = ('page.py', 'page.js', 'page.css', 'mobile.css', 'previews/sports.json',
                 'index.html', 'sale_items_chart.html', 'history.json', 'previous_data.json',
                 'price_history.json', 'scrape_health.json', 'notification_state.json')
        def hashes():
            return {n: hashlib.sha256((SOURCE/n).read_bytes()).hexdigest() if (SOURCE/n).exists() else None for n in names}
        before = hashes()
        old = BeautifulSoup((SOURCE/'sale_items_chart.html').read_text(), 'html.parser')
        with tempfile.TemporaryDirectory() as directory, patch('urllib.request.urlopen', side_effect=AssertionError('no network')):
            path = build(Path(directory)/'site')
            root = path.parent
            new = BeautifulSoup(path.read_text(), 'html.parser')
            self.assertEqual(len(new.select('header')), 1)
            self.assertEqual(new.select('iframe'), [])
            self.assertEqual(str(old.select_one('#lastScan')), str(new.select_one('#lastScan')))
            self.assertEqual([str(c) for c in old.select('.deal-card')], [str(c) for c in new.select('.deal-card')])
            self.assertEqual([x.get('href') for x in old.select('a[target="_blank"]')], [x.get('href') for x in new.select('a[target="_blank"]')])
            # Original application/search scripts and styles are unchanged. Only
            # the public config assignment/analytics are removed for safety.
            for script in old.select('script:not([src])'):
                if 'window.SKATEDEALS_ALERTS = ' not in (script.string or ''):
                    self.assertIn(str(script), str(new))
            for style in old.select('style'):
                self.assertIn(str(style), str(new))
            self.assertEqual((root/'history.json').read_bytes(), (SOURCE/'history.json').read_bytes())
            # Sports with a live catalog (sports.published_catalogs) use their real
            # page; the rest get an honest placeholder.
            import sports as engine
            live = engine.published_catalogs(SOURCE)
            pages = {'index.html', 'sale_items_chart.html'}
            for sport in ('ski', 'mtb', 'bmx'):
                name = live.get(sport) or sport + '.html'
                pages.add(name)
                page = BeautifulSoup((root/name).read_text(), 'html.parser')
                self.assertEqual(len(page.select('header')), 1)
                self.assertEqual(page.select('iframe'), [])
                if sport in live:
                    self.assertTrue(page.select('[data-part][data-store]'), f'{sport} keeps its real listings')
                    self.assertTrue((root/name).with_name('history.json').is_file())
                    config = json.loads(page.select_one('#shredHeaderConfig').string)
                    self.assertEqual(config['currentSport'], sport)
                    self.assertIn('../index.html', [s['href'] for s in config['sports']], 'links reach the root from <sport>/')
                else:
                    self.assertEqual(page.select('.deal-card'), [])
                    self.assertIn('Coming soon', page.get_text())
                    self.assertTrue(all('disabled' in b.attrs for b in page.select('.topnav-links button')))
            for name in pages:
                text = (root/name).read_text()
                self.assertNotIn('window.SKATEDEALS_ALERTS = ', text)
                self.assertNotIn('skatedeals-alerts.pchoward.workers.dev', text)
                self.assertNotIn('static.cloudflareinsights.com', text)
                self.assertIn('form-action &apos;none&apos;', text)
                self.assertIn('connect-src &apos;self&apos;', text)
                self.assertIn('noindex,nofollow', text)
            self.assertEqual({str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()},
                             pages | {'history.json', 'manifest.json'}
                             | {str(Path(live[s]).parent / 'history.json') for s in live})
        self.assertEqual(before, hashes())

    def test_preview_rejects_existing_or_production_output(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError): build(directory)
        with self.assertRaises(ValueError): build(SOURCE/'never-write-header-preview')

    def test_integration_config_is_html_safe_and_does_not_disable_real_alerts(self):
        config = {'brand': '</script><img src=x>', 'currentSport': 'skate', 'sports': []}
        html = '<html><head><script>window.SKATEDEALS_ALERTS = {live:true};</script></head><body></body></html>'
        result = inject_header(html, config)
        soup = BeautifulSoup(result, 'html.parser')
        self.assertEqual(json.loads(soup.select_one('#shredHeaderConfig').string), config)
        self.assertNotIn('<img src=x>', result)
        self.assertIn('window.SKATEDEALS_ALERTS = {live:true}', result)
        self.assertNotIn('Content-Security-Policy', result)


if __name__ == '__main__':
    unittest.main()
