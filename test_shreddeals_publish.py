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
                              'discover/view.js','discover/mtb-dirt-jump/index.html','.well-known/ucp-agent.json',
                              *{'navigation/'+sport+'-categories.json' for sport in ('skate','ski','mtb','bmx')}})
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

    def test_category_metadata_uses_published_taxonomy_order_counts_and_versions(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # The just-built output must win over a saved checkout catalog.
            (root/'sale_items_chart.html').write_text('<button data-part="Wheels" data-order="2" data-count="3"></button>'
                '<button data-part="all" data-order="0" data-count="5"></button>'
                '<button data-part="Decks" data-order="1" data-count="2"></button>'
                '<button data-part="No stock" data-order="3" data-count="0"></button>')
            html = publish(root, catalogs={}).read_text()
            metadata = root/'navigation/skate-categories.json'
            entries = json.loads(metadata.read_text())
            self.assertEqual([(x['category'],x['order'],x['count'],x['slug']) for x in entries],
                [('all',0,5,'all'),('Decks',1,2,'deck'),('Wheels',2,3,'wheel'),('No stock',3,0,'no-stock')])
            config = json.loads(BeautifulSoup(html,'html.parser').select_one('#sportConfig').string)
            url = config['sports'][0]['categoriesURL']
            self.assertEqual(url, 'navigation/skate-categories.json?v='+hashlib.sha256(metadata.read_bytes()).hexdigest()[:12])
            self.assertTrue(all('categoriesURL' not in sport for sport in config['sports'][1:]))
            self.assertLess(metadata.stat().st_size, 1024)

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
                             'discover/view.js','discover/mtb-dirt-jump/index.html','.well-known/ucp-agent.json',
                             *('navigation/'+sport+'-categories.json' for sport in ('skate','ski','mtb','bmx'))):
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
        for name in ('rebuild-page.yml', 'scrape-sports.yml', 'scrape.yml'):
            workflow = (SOURCE/'.github/workflows'/name).read_text()
            self.assertIn('python -m previews.publish', workflow)
            self.assertIn('git add index.html navigation discover', workflow)

    def test_skate_scrape_publishes_navigation_after_scraping_before_committing(self):
        import yaml
        steps = yaml.safe_load((SOURCE/'.github/workflows/scrape.yml').read_text())['jobs']['scrape']['steps']
        scrape = next(i for i, step in enumerate(steps) if step.get('run') == 'python scraper.py')
        publish_step = next(i for i, step in enumerate(steps) if step.get('run') == 'python -m previews.publish')
        commit = next(i for i, step in enumerate(steps) if 'git add index.html navigation discover' in step.get('run', ''))
        self.assertLess(scrape, publish_step)
        self.assertLess(publish_step, commit)
        self.assertEqual(steps[publish_step]['if'], steps[scrape]['if'])
        self.assertEqual(steps[publish_step]['if'], steps[commit]['if'])

    def test_demo_output_rejects_symlinks_and_skate_only_has_no_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publish(root, catalogs={})
            self.assertFalse((root/'discover').exists())
            (root/'discover').symlink_to(SOURCE/'explore', target_is_directory=True)
            with self.assertRaises(ValueError):
                publish(root, catalogs={'mtb': 'mtb/sale_items_chart.html'})

    def test_header_asset_urls_match_current_content_versions(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            soup = BeautifulSoup(publish(Path(directory)).read_text(), 'html.parser')
            for name, selector, attribute in [('navigation.css', 'link[rel=stylesheet]', 'href'),
                                              ('navigation.js', 'script[src]', 'src')]:
                version = hashlib.sha256((HERE/name).read_bytes()).hexdigest()[:12]
                self.assertEqual(soup.select_one(selector)[attribute], 'navigation/' + name + '?v=' + version)
            config = json.loads(soup.select_one('#sportConfig').string)
            self.assertEqual(config['bridgeVersion'], hashlib.sha256((HERE/'skate-bridge.js').read_bytes()).hexdigest()[:12])

    def test_category_navigation_is_one_browse_row_without_static_category_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            soup = BeautifulSoup(publish(Path(directory)).read_text(), 'html.parser')
            browse = soup.select_one('.browse-nav')
            self.assertTrue(browse.select_one('#sportTabs'))
            self.assertTrue(browse.select_one('#categoryToggle[aria-controls="categoryPanel"]'))
            self.assertEqual(soup.select('#categoryChoices button'), [])
            self.assertEqual(soup.select_one('#categoryCount').text, '')
            self.assertFalse(soup.select('.top-row #sportTabs'))

    def test_publish_rejects_symlink_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'index.html').symlink_to(SOURCE/'sale_items_chart.html')
            with self.assertRaises(ValueError):publish(root)


if __name__=='__main__':unittest.main()
