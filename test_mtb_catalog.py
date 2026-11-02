"""Isolated MTB catalog and exact variant facts; fixtures are explicitly synthetic."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
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
        with patch('stores.shopify.load_sale_products',return_value=None):
            self.assertIsNone(stores.scrapers()[0].scrape())


if __name__=='__main__':unittest.main()
