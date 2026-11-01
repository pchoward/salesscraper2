"""Precise specs: saved-data only, no live fetch, no product identity changes."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
from product_specs import enrich, numbers, durometers
from stores import exodus, spot, shopify, deathgear
from stores.ccs import CCSScraper
from stores.skatewarehouse import SkateWarehouseScraper
from stores.tactics import TacticsScraper
from history import update_price_history, _ordered_entry
from report import build_report_html

FIXTURES = Path(__file__).parent/'tests/fixtures/specifications'


def wheel(name='OJ Elite Wheels'):
    return {'name':name, 'part':'Wheels', 'store':'Exodus', 'url':'https://exodusrideshop.com/products/oj',
            'price_new':'29.95','price_old':'44.95'}


class ExactSpecsTests(unittest.TestCase):
    def test_missing_ambiguous_and_model_numbers_are_not_inferred(self):
        for name, desc in [('OJ Elite 101A Wheels',''), ('OJ Double Duro Wheels','Choose 52mm or 54mm'),
                           ('Spitfire Formula Four Wheels',''), ('OJ Wheels','Contact patch: 44mm')]:
            item=enrich(wheel(name),desc)
            self.assertNotIn('diameter_mm',item)
        deck=enrich({'name':'Heroin Curb Killer 8 Egg Skateboard Deck','part':'Decks'},
                    'Nose: 7.25 inches; Tail: 6.75 inches; Length: 32 inches; Wheelbase: 14.5 inches')
        self.assertNotIn('width',deck)
        self.assertNotIn('width',enrich({'name':'Baker Deck','part':'Decks'},'Width: 8.25 inches and Width: 8.5 inches'))

    def test_single_dimensions_and_original_hardness_notation(self):
        item=enrich(wheel(), 'Diameter: 54mm; width: 40mm; Durometer: 81B')
        self.assertEqual(item['diameter_mm'],54)
        self.assertEqual(item['durometers'],['81B'])
        self.assertEqual(durometers('99A, 101a, 81B, 99D, 80HD'),['99A','101A','81B','99D','80HD'])
        self.assertEqual(durometers('Dragon Formula'),[])

    def test_multiple_sizes_preserve_offer_prices_stock_and_identity(self):
        source=json.loads((FIXTURES/'shopify.json').read_text())['products'][1]
        item=shopify.ShopifyScraper(exodus.SHOP,'Wheels').products_from([source])[0]
        self.assertEqual(item['diameters_mm'],[52,54])
        self.assertNotIn('diameter_mm',item)
        self.assertEqual(item['name'],source['title'])
        self.assertEqual(item['url'],'https://exodusrideshop.com/products/oj-combo')
        self.assertEqual(item['price_new'],'29.95')
        self.assertEqual([(o['diameter_mm'],o['price'],o['available']) for o in item['spec_offers']],
                         [(52,29.95,True),(54,34.95,True)])
        self.assertEqual(item['durometers'],['99A','101A'])

    def test_exodus_single_width_variant_does_not_create_new_identity(self):
        source=json.loads((FIXTURES/'shopify.json').read_text())['products'][0]
        items=shopify.ShopifyScraper(exodus.SHOP,'Decks').products_from([source])
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['width'],8.25)
        self.assertNotIn('?variant',items[0]['url'])
        self.assertEqual(items[0]['name'],source['title'])

    def test_spot_table_width_and_deathgear_body(self):
        source=json.loads((FIXTURES/'shopify.json').read_text())['products'][2]
        item=shopify.ShopifyScraper(spot.SHOP,'Decks').products_from([source])[0]
        self.assertEqual(item['width'],8.375)
        source=json.loads((FIXTURES/'deathgear.json').read_text())['items']
        item=deathgear.DeathgearScraper('Decks').products_from(source)[0]
        self.assertEqual(item['width'],10.25)
        self.assertEqual(item['name'],'Heroin Questions Heavy Haulage Skateboard Deck')
        self.assertEqual(item['url'],'https://www.deathgearproducts.com/shop/p/heavy-haulage')

    def test_html_retailers_extract_card_scoped_data_without_requests(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('unexpected request')):
            cases=[(SkateWarehouseScraper('SkateWarehouse','https://www.skatewarehouse.com','Decks'),'skatewarehouse.html','width',9.9),
                   (SkateWarehouseScraper('SkateWarehouse','https://www.skatewarehouse.com','Wheels'),'skatewarehouse.html','diameters_mm',[52,54]),
                   (CCSScraper('CCS','https://shop.ccs.com','Wheels'),'ccs.html','diameter_mm',54),
                   (TacticsScraper('Tactics','https://www.tactics.com','Wheels'),'tactics.html','diameter_mm',54)]
            for scraper, file, key, expected in cases:
                with self.subTest(retailer=scraper.name,part=scraper.part), patch('stores.browser.safe_write_file'):
                    items=scraper.parse((FIXTURES/file).read_text())
                    self.assertEqual(len(items),1)
                    self.assertEqual(items[0][key],expected)
                    if scraper.name=='CCS':
                        self.assertEqual(items[0]['spec_offers'][0]['price'],29.95)

    def test_multiwidth_product_keeps_existing_unsplit_identity(self):
        source=json.loads((FIXTURES/'shopify.json').read_text())['products'][0]
        source['options']=[{'name':'Width'},{'name':'Color'}]
        source['variants']=[dict(id=index, title=f'{width} / {color}', option1=width, option2=color,
                                 available=True, price=price, compare_at_price='69.95')
                            for index,(width,color,price) in enumerate([
                                ('8.25','Black','49.95'),('8.5','Black','54.95'),
                                ('8.25','White','49.95'),('8.5','White','54.95')],1)]
        items=shopify.ShopifyScraper(exodus.SHOP,'Decks').products_from([source])
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['widths'],[8.25,8.5])
        self.assertNotIn('width',items[0])
        self.assertNotIn('?variant',items[0]['url'])
        self.assertEqual([o['price'] for o in items[0]['spec_offers']],[49.95,54.95,49.95,54.95])

    def test_fractional_width_and_ranges_are_not_confused(self):
        self.assertEqual(enrich({'name':'Baker Deck','part':'Decks'},'Width: 8 1/4 inches')['width'],8.25)
        self.assertNotIn('width',enrich({'name':'Baker Deck','part':'Decks'},'Width: 8.25-8.5 inches'))
        self.assertNotIn('diameter_mm',enrich(wheel('OJ Wheels 52-54mm')))
        self.assertEqual(enrich(wheel(),'Durometer: 99A/95A')['durometers'],['99A','95A'])

    def test_second_enrichment_clears_previously_named_sold_out_sizes(self):
        item=enrich(wheel('OJ Wheels 54mm 99A'))
        enrich(item, product={'options':[{'name':'Diameter'}]},
               variants=[{'option1':'54','available':False}])
        self.assertNotIn('diameters_mm',item)
        self.assertNotIn('diameter_mm',item)
        self.assertNotIn('durometers',item)

    def test_unknown_availability_and_conflict_remain_explicit(self):
        item=enrich(wheel('OJ Wheels 52mm'), product={'options':[{'name':'Diameter'}]},
                    variants=[{'id':1,'option1':'54','price':'39','compare_at_price':'49'}])
        self.assertEqual(item['diameter_mm'],54)
        self.assertIsNone(item['spec_offers'][0]['available'])
        self.assertTrue(item['spec_conflicts'])
        unknown=enrich(wheel(), variants=[{'title':'52mm / 54mm','price':'39'}])
        self.assertNotIn('diameter_mm',unknown)
        self.assertEqual(unknown['spec_conflicts'],['ambiguous variant size'])
        label=enrich(wheel(), product={'options':[{'name':'Color'}]},variants=[{'option1':'54'}])
        self.assertNotIn('diameter_mm',label)

    def test_units_and_durometer_conflicts_do_not_create_equivalences(self):
        self.assertNotIn('width',enrich({'name':'Baker Deck','part':'Decks'},'Width: 8.25cm'))
        self.assertNotIn('diameter_mm',enrich(wheel(),'Diameter: 54 cm'))
        self.assertNotIn('diameter_mm',enrich(wheel('OJ Wheels Width 54mm')))
        self.assertNotIn('diameter_mm',enrich(wheel(), product={'options':[{'name':'Diameter (cm)'}]}, variants=[{'option1':'54'}]))
        deck=enrich({'name':'Baker Deck','part':'Decks'},product={'options':[{'name':'Width'}]},variants=[{'option1':'8.25mm'}])
        self.assertNotIn('width',deck)
        item=enrich(wheel('OJ Wheels 99A'),product={'options':[{'name':'Hardness'}]},variants=[{'option1':'81B'}])
        self.assertEqual(item['durometers'],['81B'])
        self.assertIn('variant hardness differs from title; explicit option used',item['spec_conflicts'])
        self.assertEqual(enrich(wheel('OJ Wheels 99A'),'Durometer: 99A/95A')['durometers'],['99A','95A'])

    def test_all_sold_out_options_never_become_available_sizes(self):
        item=enrich(wheel(), product={'options':[{'name':'Diameter'}]},variants=[{'option1':'54','available':False}])
        self.assertNotIn('diameters_mm',item)
        self.assertFalse(item['spec_offers'][0]['available'])

    def test_cruiser_exclusions_stay_intact(self):
        product=json.loads((FIXTURES/'shopify.json').read_text())['products'][0]
        product['title']='DGK Cruiser Longboard Deck'
        self.assertEqual(shopify.ShopifyScraper(exodus.SHOP,'Decks').products_from([product]),[])

    def test_spec_enrichment_does_not_reset_price_history(self):
        item=wheel(); before=update_price_history({'Exodus_Wheels':[item]}, {}, today='2026-10-30')
        old=copy.deepcopy(before[item['url']])
        enrich(item,'Diameter: 54mm; hardness: 99A')
        after=update_price_history({'Exodus_Wheels':[item]}, before, today='2026-11-01')[item['url']]
        self.assertEqual(after['first_seen'],old['first_seen'])
        self.assertEqual(after['prices']['2026-10-30'],old['prices']['2026-10-30'])
        self.assertNotIn('earlier_products',after)
        self.assertEqual(_ordered_entry(after)['diameters_mm'],[54])

    def test_existing_deck_detail_fetch_is_reused_without_more_requests(self):
        from stores.details import fill_wheelbases
        item={'name':'Heroin Questions Deck','part':'Decks','store':'Deathgear','url':'https://www.deathgearproducts.com/shop/p/test'}
        history={item['url']:{'name':item['name']}}
        fetch=lambda url,accept:'<p>Width: 10.25 inches; Wheelbase: 14.5 inches; Length: 32 inches</p>'
        with patch('stores.details.page_text', return_value='Width: 10.25 inches Wheelbase: 14.5 inches') as page:
            self.assertEqual(fill_wheelbases({'Deathgear_Decks':[item]},history,today='2026-11-01',fetch=fetch,sleep=lambda _:None),(1,1))
        page.assert_called_once()
        self.assertEqual(item['width'],10.25)
        self.assertEqual(history[item['url']]['width'],10.25)

    def test_malformed_optional_specification_does_not_fail_product(self):
        item=wheel()
        enrich(item,product={'options':4},variants=[{'title':'54mm'}])
        self.assertEqual(item,wheel())

    def test_audit_is_read_only_and_does_not_infer_from_model_names(self):
        from audit.specifications import coverage
        catalog={'Exodus_Wheels':[wheel('OJ Elite Wheels'),wheel('Spitfire Wheels 54mm 99A')]}
        before=copy.deepcopy(catalog)
        with patch('urllib.request.urlopen',side_effect=AssertionError('no requests')):
            report=coverage(catalog,replay_text=True)
        self.assertEqual(report['retailers']['Exodus']['missing_diameter'],1)
        self.assertEqual(report['retailers']['Exodus']['missing_durometer'],1)
        self.assertEqual(catalog,before)

    def test_renderer_and_search_use_precise_offer_metadata(self):
        product=json.loads((FIXTURES/'shopify.json').read_text())['products'][1]
        item=shopify.ShopifyScraper(exodus.SHOP,'Wheels').products_from([product])[0]
        html=build_report_html({'Exodus_Wheels':[item]}, {}, generated_at='2026-11-01T10:00:00+00:00')
        soup=BeautifulSoup(html,'html.parser')
        row=soup.select_one('[data-part="Wheels"][data-spec-offers]')
        self.assertIsNotNone(row)
        data={k[5:].replace('spec-offers','specOffers'):v for k,v in row.attrs.items() if k.startswith('data-')}
        script='''const assert=require('node:assert/strict');const S=require('./search/search.js');
const row={dataset:JSON.parse(process.argv[1])};
assert.equal(S.rowAllows({diameter:54},row),true);
assert.equal(S.rowAllows({diameter:56},row),false);
assert.equal(S.rowAllows({diameter:54,priceMax:30},row),false);
assert.equal(S.rowAllows({diameter:54,priceMax:35},row),true);
assert.equal(S.rowAllows({diameter:52,duros:['101a']},row),false);
assert.equal(S.rowAllows({diameter:54,duros:['101a']},row),true);
assert.equal(S.rowAllows({diameter:54,discountMin:30},row),false);
assert.equal(S.rowAllows({diameter:52,discountMin:30},row),true);
assert.equal(S.rowAllows({diameter:54},{name:'Legacy Wheel 54mm'}),true);
assert.equal(S.rowAllows({diameter:54},{name:'Band 52-54mm Wheels'}),false);
assert.equal(S.rowAllows({diameter:50},{name:'Product 150mm'}),false);
assert.equal(S.duroToA('80HD'),'');
assert.equal(S.rowAllows({width:8.5},{widths:'8.25,8.5'}),true);
assert.equal(S.rowAllows({width:8.75},{widths:'8.25,8.5'}),false);
'''
        result=subprocess.run(['node','-e',script,json.dumps(data)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
