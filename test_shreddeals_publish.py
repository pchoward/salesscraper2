"""Production shell uses the live public Skate page, with no copied/stale catalog."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
from previews.publish import publish
from previews.shreddeals import HERE, SOURCE
from report import build_report_html


class ProductionNavigationTests(unittest.TestCase):
    def test_publish_writes_only_public_assets_with_live_skate_reference(self):
        with tempfile.TemporaryDirectory() as directory,patch('urllib.request.urlopen',side_effect=AssertionError('no network')):
            root=Path(directory)
            path=publish(root)
            self.assertEqual({str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()},
                             {'index.html','navigation/navigation.js','navigation/navigation.css','navigation/skate-bridge.js',
                              'discover/view.js','discover/mtb-dirt-jump/index.html'})
            html=path.read_text();soup=BeautifulSoup(html,'html.parser')
            config=json.loads(soup.select_one('#sportConfig').string)
            self.assertTrue(config['production'])
            self.assertEqual([s['id'] for s in config['sports']],['skate','ski','mtb','bmx'])
            self.assertEqual(config['sports'][0]['catalog'],'sale_items_chart.html')
            self.assertNotIn('Development prototype',html)
            self.assertNotIn('live delivery is disabled',html)
            self.assertTrue(soup.select_one('noscript a[href="sale_items_chart.html"]'))
            # Other sports get a tab once their catalog has listings (sports.published_catalogs).
            import sports
            live=sports.published_catalogs(SOURCE)
            for sport in config['sports'][1:]:self.assertEqual(sport['catalog'],live.get(sport['id']))
            for name in ('navigation.js','navigation.css','skate-bridge.js'):
                self.assertEqual((root/'navigation'/name).read_bytes(),(HERE/name).read_bytes())

    def test_standalone_skate_only_loads_bridge_when_embedded(self):
        html=build_report_html({}, {}, generated_at='2026-10-31T10:00:00+00:00')
        self.assertIn('window.parent!==window&&!window.shredBridgeInstalled',html)
        self.assertIn('bridge.src="navigation/skate-bridge.js"',html)
        self.assertNotIn('sportTabs',html)
        bridge=(HERE/'skate-bridge.js').read_text()
        self.assertIn('if (window.parent === window || window.shredBridgeInstalled) return;',bridge)
        self.assertIn('else send("replace")',bridge)

    def test_checked_in_public_assets_are_current_and_pages_can_serve_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);publish(root)
            for relative in ('index.html','navigation/navigation.js','navigation/navigation.css','navigation/skate-bridge.js',
                             'discover/view.js','discover/mtb-dirt-jump/index.html'):
                self.assertEqual((root/relative).read_bytes(),(SOURCE/relative).read_bytes())
        config=(SOURCE/'_config.yml').read_text()
        self.assertNotIn('  - "index.html"',config)
        self.assertNotIn('  - "navigation"',config)
        workflow=(SOURCE/'.github/workflows/rebuild-page.yml').read_text()
        self.assertIn('python -m previews.publish',workflow)
        self.assertIn('index.html navigation',workflow)

    def test_public_demo_survives_republication_without_exposing_internal_files(self):
        import yaml
        with tempfile.TemporaryDirectory() as directory, patch('urllib.request.urlopen', side_effect=AssertionError('no network')):
            root = Path(directory)
            publish(root, catalogs={'mtb': 'mtb/sale_items_chart.html'})
            first = (root/'discover/mtb-dirt-jump/index.html').read_bytes()
            publish(root, catalogs={'mtb': 'mtb/sale_items_chart.html'})
            self.assertEqual(first, (root/'discover/mtb-dirt-jump/index.html').read_bytes())
            soup = BeautifulSoup(first, 'html.parser')
            payload = json.loads(soup.select_one('#exploreData').string)
            self.assertTrue(payload['scope']['demo'])
            self.assertEqual(payload['state']['manifest'], [])
            self.assertEqual(payload['state']['history'], {})
            self.assertIn('DEMO / SAMPLE PRODUCTS', soup.select_one('.preview-note').text)
            config = json.loads(BeautifulSoup((root/'index.html').read_text(), 'html.parser').select_one('#sportConfig').string)
            self.assertEqual(config['defaultSport'], 'skate')
            self.assertEqual(config['exploreScopes'], [{'id': 'mtb-dirt-jump', 'sport': 'mtb', 'catalog': 'discover/mtb-dirt-jump/index.html', 'demo': True}])
            self.assertFalse((root/'explore').exists())
            self.assertFalse(any(root.rglob('*.py')))
        excluded = yaml.safe_load((SOURCE/'_config.yml').read_text())['exclude']
        self.assertIn('explore', excluded)
        self.assertIn('test_explore.py', excluded)
        self.assertNotIn('discover', excluded)
        for name in ('rebuild-page.yml', 'scrape-sports.yml'):
            workflow = (SOURCE/'.github/workflows'/name).read_text()
            self.assertIn('python -m previews.publish', workflow)
            self.assertIn('git add index.html navigation discover', workflow)

    def test_demo_output_rejects_symlinks_and_skate_only_has_no_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publish(root, catalogs={})
            self.assertFalse((root/'discover').exists())
            (root/'discover').symlink_to(SOURCE/'explore', target_is_directory=True)
            with self.assertRaises(ValueError):
                publish(root, catalogs={'mtb': 'mtb/sale_items_chart.html'})

    def test_publish_rejects_symlink_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'index.html').symlink_to(SOURCE/'sale_items_chart.html')
            with self.assertRaises(ValueError):publish(root)


if __name__=='__main__':unittest.main()
