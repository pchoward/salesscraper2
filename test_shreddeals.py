"""Issue #111 navigation and isolation checks; no scrape, deploy or live delivery."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
from previews.shreddeals import SOURCE,HERE,build,load_config,skate_query_keys


class ShredDealsTests(unittest.TestCase):
    def test_navigation_config_covers_four_sports_without_segmentation(self):
        config=load_config(HERE/'sports.json')
        self.assertEqual([sport['label'] for sport in config['sports']],['Skate','Ski','MTB','BMX'])
        for sport in config['sports']:
            self.assertNotIn('disciplines',sport)
            if sport['id']!='skate':
                self.assertIsNone(sport['catalog'])
                self.assertEqual(sport['categories'],[])
        self.assertIsNone(config['brand']['domain'])
        self.assertEqual(config['sports'][0]['facets']['Decks'][:2],['brand','width'])

    def test_sport_switching_discards_old_discipline_and_preserves_legacy_parameters(self):
        script='''const assert=require('node:assert/strict');const N=require('./previews/navigation.js');
const config=JSON.parse(process.argv[1]);config.skateQueryKeys=JSON.parse(process.argv[2]);
const start='https://preview.example/index.html?sport=bmx&discipline=freestyle&store=CCS&width=8.25&q=baker&utm_source=test#kept';
const bmx=N.state(start,config);assert.equal(bmx.sport.id,'bmx');assert.equal(bmx.discipline,undefined);
const ski=N.navigate(start,config,'ski');assert.equal(ski.searchParams.get('discipline'),null);
assert.equal(ski.searchParams.get('q'),'baker');assert.equal(ski.hash,'#kept');
assert.equal(N.state(N.navigate(ski,config,'ski'),config).sport.id,'ski');
assert.equal(N.state(start,config).sport.id,'bmx','back/forward restores sport');
assert.equal(N.state('https://preview.example/?sport=unknown&discipline=dirt',config).sport.id,'skate');
assert.equal(N.state('https://preview.example/?sport=skate&discipline=dirt',config).discipline,undefined);
const frame=N.skateURL(start,config);assert.equal(frame.pathname,'/skate/sale_items_chart.html');
assert.equal(frame.searchParams.get('sport'),null);assert.equal(frame.searchParams.get('discipline'),null);
assert.equal(frame.searchParams.get('store'),'CCS');assert.equal(frame.searchParams.get('width'),'8.25');
const merged=N.mergeSkateURL(start,'https://preview.example/skate/sale_items_chart.html?store=Tactics&q=oj#after',config);
assert.equal(merged.searchParams.get('sport'),'bmx');assert.equal(merged.searchParams.get('discipline'),null);
assert.equal(merged.searchParams.get('store'),'Tactics');assert.equal(merged.searchParams.get('width'),null);
assert.equal(merged.searchParams.get('utm_source'),'test','unknown parameters survive child normalization');
assert.equal(merged.hash,'#after');
assert.throws(()=>N.mergeSkateURL(start,'https://attacker.example/skate/sale_items_chart.html',config));
assert.throws(()=>N.mergeSkateURL(start,'https://preview.example/other.html',config));
assert.equal(N.nextIndex(3,'ArrowRight',4),0);assert.equal(N.nextIndex(0,'ArrowLeft',4),3);
assert.equal(N.nextIndex(2,'Home',4),0);assert.equal(N.nextIndex(2,'End',4),3);assert.equal(N.nextIndex(2,'Tab',4),null);
// Navigation does not hardcode four sports or their labels in rendering logic.
config.sports.push({id:'surf',label:'Surf',catalog:null});
assert.equal(N.state(N.navigate(start,config,'surf'),config).sport.label,'Surf');
'''
        result=subprocess.run(['node','-e',script,json.dumps(load_config(HERE/'sports.json')),json.dumps(skate_query_keys())],
                              cwd=SOURCE,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_build_preserves_original_inline_application_and_production_files(self):
        names=('sale_items_chart.html','history.json','previous_data.json','price_history.json','scrape_health.json',
               'notification_state.json','notification_state.json.lock')
        def hashes():
            return {name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() if (SOURCE/name).exists() else None for name in names}
        before=hashes()
        with tempfile.TemporaryDirectory() as directory,patch('urllib.request.urlopen',side_effect=AssertionError('no network')):
            path=build(Path(directory)/'preview')
            root=path.parent
            old=BeautifulSoup((SOURCE/'sale_items_chart.html').read_text(),'html.parser')
            new=BeautifulSoup((root/'skate/sale_items_chart.html').read_text(),'html.parser')
            self.assertEqual([x.string for x in old.select('style')],[x.string for x in new.select('style')])
            self.assertEqual([x.string for x in old.select('script:not([src])')], [x.string for x in new.select('script:not([src])')])
            self.assertEqual(len(old.select('.deal-card')),len(new.select('.deal-card')))
            self.assertEqual([x.get('href') for x in old.select('a[target="_blank"]')], [x.get('href') for x in new.select('a[target="_blank"]')])
            self.assertEqual((root/'skate/history.json').read_bytes(),(SOURCE/'history.json').read_bytes())
            self.assertFalse((root/'previous_data.json').exists())
            self.assertFalse((root/'price_history.json').exists())
            self.assertNotIn('static.cloudflareinsights.com',str(new.select('script[src]')))
            self.assertIn("connect-src &apos;self&apos;",(root/'skate/sale_items_chart.html').read_text())
            manifest=json.loads((root/'manifest.json').read_text())
            self.assertTrue(manifest['development_only'])
            for sport in ('bmx','ski','mtb'):self.assertIsNone(manifest['catalogs'][sport])
            # Existing Brand section precedes the dimension context; it is not rebuilt.
            group=new.select_one('#specGroup')
            self.assertTrue(group.find_all(recursive=False)[0].select_one('#brandFacet'))
            self.assertEqual(group.find_all(recursive=False)[1].get('id'),'contextSpecs')
        self.assertEqual(before,hashes())

    def test_unsafe_and_duplicate_output_paths_are_rejected(self):
        for path in (SOURCE/'prototype',SOURCE):
            with self.assertRaises(ValueError):build(path)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            link=root/'link';link.symlink_to(SOURCE,target_is_directory=True)
            with self.assertRaises(ValueError):build(link)
            with self.assertRaises(ValueError):build(root)

    def test_new_local_dependencies_fail_before_partial_output_is_written(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';source.mkdir()
            (source/'history.json').write_text('{"items":{}}')
            (source/'sale_items_chart.html').write_text('<html><head><link rel="stylesheet" href="new.css"></head><body></body></html>')
            output=root/'preview'
            with self.assertRaises(ValueError):build(output,source=source)
            self.assertFalse(output.exists())

    def test_invalid_config_cannot_attach_skate_inventory_to_another_sport(self):
        config=load_config(HERE/'sports.json')
        config['sports'][1]['catalog']='skate/sale_items_chart.html'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'sports.json';path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):load_config(path)

    def test_generated_shell_is_accessible_and_configuration_is_escaped(self):
        config=load_config(HERE/'sports.json')
        config['brand']['name']='Alternate </script> brand'
        config['brand']['domain']='deals.example'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);custom=root/'config.json';custom.write_text(json.dumps(config))
            path=build(root/'preview',config_path=custom)
            soup=BeautifulSoup(path.read_text(),'html.parser')
            payload=json.loads(soup.select_one('#sportConfig').string)
            self.assertEqual(payload['brand'],config['brand'])
            self.assertEqual(len(soup.select('[role="tablist"]')),1)
            self.assertTrue(soup.select_one('#skateFrame').has_attr('hidden'))
            self.assertIn('Coming soon / no catalog yet',soup.get_text())
            self.assertTrue(soup.select_one('a.skip'))
            self.assertEqual(soup.select_one('main').parent.name,'body')
            self.assertEqual(soup.select_one('#skateFrame').parent.get('id'),'catalogPanel')
        css=(HERE/'navigation.css').read_text()
        self.assertIn(':focus-visible',css)
        self.assertIn('@media(max-width:600px)',css)
        self.assertIn('repeat(4,1fr)',css)
        self.assertNotIn('disciplineTabs',css)
        js=(HERE/'navigation.js').read_text()
        self.assertIn('event.source !== frame.contentWindow',js)
        self.assertIn('event.origin !== win.location.origin',js)
        self.assertNotIn('disciplineTabs',js)
        self.assertNotIn('disciplinePanel',js)


if __name__=='__main__':unittest.main()
