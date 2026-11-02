"""Isolated MTB catalog and exact variant facts; fixtures are explicitly synthetic."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import subprocess
import tempfile
import hashlib
from unittest.mock import patch

import sports
from sports.mtb import stores
from sports.mtb.rules import title_part,filter_reason
from sports.mtb.specs import extract

FIXTURE=Path(__file__).parent/'tests/fixtures/mtb/shopify-synthetic.json'


class MtbCatalogTests(unittest.TestCase):
    def feed(self):return json.loads(FIXTURE.read_text())['products']

    def test_both_exact_collections_reuse_the_shared_parser_and_keep_only_sale_equipment(self):
        self.assertEqual([s.sale_json for s in stores.STORES],[
            'https://www.worldwidecyclery.com/collections/deals/products.json',
            'https://www.fanatikbike.com/collections/fanatik-outlet/products.json'])
        with sports.MTB.active(),patch('stores.shopify._fetch_json',side_effect=AssertionError('fixtures must not fetch')):
            for shop in stores.STORES:
                items=[item for parser in stores.scrapers() if parser.shop==shop for item in parser.products_from(self.feed())]
                self.assertEqual(len(items),6)
                self.assertEqual(len({i['url'] for i in items}),6)
                self.assertFalse(any('jersey' in i['url'] or 'road' in i['url'] or 'sold-out' in i['url'] for i in items))
                tire=next(i for i in items if i['part']=='Tires')
                self.assertEqual(tire['price_new'],'40.00')
                self.assertEqual(tire['technical_specs']['wheel_size'],['27.5','29'])
                self.assertEqual([o['variant_id'] for o in tire['technical_offers']],[11,12])
                unknown=next(i for i in items if 'unknown-stock' in i['url'])
                self.assertEqual(unknown['availability'],'Check store')
                self.assertEqual(tire['availability'],'In stock')

    def test_precise_specs_do_not_turn_offset_or_shock_stroke_into_travel(self):
        p=self.feed()[1]
        specs,warnings=extract(p,p['variants'][0],'Forks & Shocks')
        self.assertEqual(specs['travel_mm'],['160'])
        self.assertEqual(specs['wheel_size'],['29'])
        self.assertEqual(specs['axle'],['15x110mm'])
        self.assertEqual(warnings,[])
        specs,_=extract({'title':'Rear Shock 210 x 55mm'}, {}, 'Forks & Shocks')
        self.assertNotIn('travel_mm',specs)
        specs,_=extract({'title':'Trail Frame Size: 29 inches'}, {}, 'Frames')
        self.assertNotIn('wheel_size',specs)
        specs,_=extract({'title':'Suspension Fork','product_type':'Forks','body_html':'<table><tr><th>Wheel Size</th><td>29 inches</td></tr><tr><th>Travel</th><td>160mm</td></tr></table>'},{},'Forks & Shocks')
        self.assertEqual(specs['wheel_size'],['29'])
        self.assertEqual(specs['travel_mm'],['160'])

    def test_conflicting_or_ambiguous_specs_are_not_invented(self):
        p={'title':'Fork 29 inches','options':[{'name':'Wheel Size'}]}
        specs,warnings=extract(p,{'option1':'27.5 inches'},'Forks & Shocks')
        self.assertNotIn('wheel_size',specs)
        self.assertIn('conflicting wheel_size',warnings)
        specs,_=extract({'title':'Unknown frame','options':[{'name':'Frame Size'}]}, {'option1':'Unspecified'}, 'Frames')
        self.assertEqual(specs,{})
        self.assertIsNone(title_part('Model X 170'))
        self.assertIsNotNone(filter_reason('Road Cycling Helmet','Protection'))

    def test_failure_remains_none_and_sport_state_defaults_stay_separate(self):
        self.assertEqual(sports.MTB.scrapers,'sports.mtb.stores:scrapers')
        self.assertEqual(sports.MTB.page_path,'mtb/sale_items_chart.html')
        self.assertEqual(sports.MTB.data_dir,'catalogs/mtb')
        self.assertFalse(sports.MTB.delivery)
        self.assertEqual(sports.BMX.scrapers,'sports.bmx.stores:scrapers')
        self.assertTrue(sports.SKATE.delivery)
        with patch('sports.mtb.stores.robots_policy',return_value=None):
            self.assertIsNone(stores.scrapers()[0].scrape())

    def test_robots_and_pagination_are_cached_per_store_without_partial_success(self):
        from urllib import robotparser
        robots=robotparser.RobotFileParser();robots.parse(['User-agent: *','Allow: /'])
        shop=deepcopy(stores.WORLDWIDE);shop.cache={}
        parsers=[stores.MtbShopifyScraper(shop,p) for p in ('Tires','Frames')]
        known=self.feed();known[8]['variants'][0]['available']=True
        with sports.MTB.active(),patch('sports.mtb.stores.robots_policy',return_value=(robots,0)) as policy, \
             patch('stores.shopify._fetch_json',return_value={'products':known}) as fetch:
            self.assertEqual(len(parsers[0].scrape()),1)
            self.assertEqual(len(parsers[1].scrape()),1)
            self.assertEqual(fetch.call_count,1);self.assertEqual(policy.call_count,1)
        shop.cache={}
        batch=self.feed()*25
        with sports.MTB.active(),patch('sports.mtb.stores.robots_policy',return_value=(robots,0)), \
             patch('stores.shopify._fetch_json',side_effect=[{'products':batch},None]),patch('stores.shopify.time.sleep'):
            self.assertIsNone(parsers[0].scrape())
            self.assertIsNone(parsers[1].scrape())
        shop.cache={}
        robots=robotparser.RobotFileParser();robots.parse(['User-agent: *','Disallow: /'])
        with patch('sports.mtb.stores.robots_policy',return_value=(robots,0)),patch('stores.shopify._fetch_json') as fetch:
            self.assertIsNone(parsers[0].scrape());fetch.assert_not_called()

    def test_unknown_stock_is_checked_once_or_left_unknown_without_failing_store(self):
        from urllib import robotparser
        robots=robotparser.RobotFileParser();robots.parse(['User-agent: *','Allow: /'])
        shop=deepcopy(stores.WORLDWIDE);shop.cache={}
        parser=stores.MtbShopifyScraper(shop,'Cockpit')
        with sports.MTB.active(),patch('sports.mtb.stores.robots_policy',return_value=(robots,0)), \
             patch('stores.shopify._fetch_json',side_effect=[{'products':self.feed()},{'variants':[{'id':91,'available':False}]}]) as get:
            self.assertEqual(parser.scrape(),[])
            self.assertEqual(get.call_count,2)
        shop.cache={}
        with sports.MTB.active(),patch('sports.mtb.stores.robots_policy',return_value=(robots,0)), \
             patch('stores.shopify._fetch_json',side_effect=[{'products':self.feed()},None]):
            self.assertEqual(parser.scrape()[0]['availability'],'Check store')
        shop.cache={}
        with sports.MTB.active(),patch('sports.mtb.stores.robots_policy',return_value=(robots,0)), \
             patch('sports.mtb.stores.MAX_STOCK_LOOKUPS',0),patch('stores.shopify._fetch_json',return_value={'products':self.feed()}) as get:
            self.assertEqual(parser.scrape()[0]['availability'],'Check store')
            self.assertEqual(get.call_count,1)

    def test_invalid_stock_fields_do_not_turn_unknown_into_sold_out(self):
        from urllib import robotparser
        robots=robotparser.RobotFileParser();robots.parse(['User-agent: *','Allow: /'])
        shop=deepcopy(stores.WORLDWIDE);shop.cache={}
        with sports.MTB.active(),patch('sports.mtb.stores.robots_policy',return_value=(robots,0)), \
             patch('stores.shopify._fetch_json',side_effect=[{'products':self.feed()},{'variants':[{'id':91}]}]):
            items=stores.MtbShopifyScraper(shop,'Cockpit').scrape()
            self.assertEqual(items[0]['availability'],'Check store')

    def test_unmapped_sale_equipment_is_not_successful_empty_catalog(self):
        from urllib import robotparser
        robots=robotparser.RobotFileParser();robots.parse(['User-agent: *','Allow: /'])
        shop=deepcopy(stores.WORLDWIDE);shop.cache={}
        feed=[{'title':'Unclassified Model','handle':'unknown','product_type':'Unknown Equipment',
               'variants':[{'id':1,'price':'10','compare_at_price':'20','available':True}]}]
        with sports.MTB.active(),patch('sports.mtb.stores.robots_policy',return_value=(robots,0)), \
             patch('stores.shopify._fetch_json',return_value={'products':feed}):
            self.assertIsNone(stores.MtbShopifyScraper(shop,'Bikes').scrape())

    def test_frontend_facets_use_same_variant_for_all_specs_and_price(self):
        from sports.mtb.facets import payload
        with sports.MTB.active():
            data={s.name+'_'+s.part:s.products_from(self.feed()) for s in stores.scrapers()}
            config=payload(data)
        script=r"""
const assert=require('assert');
const create=require('./previews/sport-filters.js');
const config=JSON.parse(process.argv[1]),f=create(config);
const url='https://www.worldwidecyclery.com/products/fixture-trail-tire';
f.restore({wheel_size:'29'});
assert.equal(f.price(url).price,55);assert.equal(f.price(url).compare,90);
f.restore({wheel_size:'29',tire_width:'2.4'});
assert.equal(f.allows(url),false); // 29 x 2.4 is sold out, not a fabricated cross-variant match.
f.restore({wheel_size:'27.5',tire_width:'2.4'});
assert.equal(f.price(url).price,40);
const params=new URLSearchParams('q=tire&store=worldwide');f.encode(params,f.capture());
assert.equal(params.get('mtb_wheel'),'27.5');assert.equal(params.get('q'),'tire');
f.restore(f.decode(params));assert.equal(f.capture().tire_width,'2.4');
f.clear();assert.equal(f.price(url),null);assert.equal(f.allows(url),true);
"""
        result=subprocess.run(['node','-e',script,json.dumps(config)],cwd=Path(__file__).parent,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_renderer_has_actual_mtb_controls_and_no_skate_size_controls(self):
        from bs4 import BeautifulSoup
        from report import build_report_html
        with sports.MTB.active():data={s.name+'_'+s.part:s.products_from(self.feed()) for s in stores.scrapers()}
        html=build_report_html(data,{},generated_at='2026-11-02T00:00:00+00:00',sport=sports.MTB)
        soup=BeautifulSoup(html,'html.parser')
        self.assertIsNotNone(soup.select_one('#tech-wheel_size'))
        self.assertIsNotNone(soup.select_one('#tech-travel_mm'))
        self.assertIsNotNone(soup.select_one('#tech-frame_size'))
        self.assertIsNotNone(soup.select_one('#tech-tire_width'))
        self.assertIsNone(soup.select_one('#sizeFilters'))
        self.assertEqual(len(soup.select('.deal-card')),12)
        self.assertNotIn('window.SKATEDEALS_ALERTS = ',html)
        skate=build_report_html({}, {}, sport=sports.SKATE)
        bmx=build_report_html({}, {}, sport=sports.BMX)
        self.assertNotIn('id="technicalCatalog"',skate)
        self.assertIn('id="technicalCatalog"',bmx)

    def test_preview_isolation_and_explicit_fixture_label(self):
        from previews.mtb_catalog import build
        from previews.shreddeals import SOURCE
        names=('previous_data.json','price_history.json','scrape_health.json','notification_state.json',
               'index.html','sale_items_chart.html','history.json')
        def hashes():
            return {n:hashlib.sha256((SOURCE/n).read_bytes()).hexdigest() if (SOURCE/n).exists() else None for n in names}
        before=hashes()
        with tempfile.TemporaryDirectory() as directory,patch('urllib.request.urlopen',side_effect=AssertionError('no fetching')):
            output=Path(directory)/'review'
            home=build(output,fixture=True)
            manifest=json.loads((output/'review-manifest.json').read_text())
            self.assertTrue(manifest['synthetic'])
            self.assertFalse(manifest['delivery'])
            self.assertEqual(manifest['mtb_listings'],12)
            self.assertIn('SYNTHETIC FIXTURE', (output/'mtb/sale_items_chart.html').read_text()[-500:])
            with self.assertRaises(ValueError):build(Path(directory)/'no-real-state')
        self.assertEqual(before,hashes())


if __name__=='__main__':unittest.main()
