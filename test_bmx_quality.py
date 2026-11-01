"""BMX-only quality changes: real saved snapshot plus labeled synthetic feeds."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sports
from filters import filter_reason
from health import empty_state
from history import (apply_lifecycle, prune_price_history, recently_gone,
                     record_misses, update_price_history)
from pipeline import prepare_run
from sports.bmx import stores
from sports.bmx.audit import classify, price_evidence
from sports.bmx.quality import scope_reason, specifications

FIXTURES = Path(__file__).parent/'tests/fixtures/bmx'


def snapshot():
    return (json.loads((FIXTURES/'albes-previous_data.json').read_text()),
            json.loads((FIXTURES/'albes-price_history.json').read_text()))


class BmxScopeTests(unittest.TestCase):
    def test_actual_snapshot_filters_only_the_nine_explicit_scope_mismatches(self):
        data, history = snapshot()
        before = deepcopy((data, history))
        selected, audit = classify(data, history)
        self.assertEqual(sum(audit['before'].values()), 72)
        self.assertEqual(sum(audit['after'].values()), 63)
        self.assertEqual(len(audit['excluded']), 9)
        self.assertEqual(audit['specs_known'], 3)
        self.assertEqual(audit['specs_unknown'], 60)
        self.assertEqual(len({i['url'] for v in selected.values() for i in v}), 63)
        self.assertEqual((data, history), before)
        with sports.BMX.active():
            self.assertTrue(all(filter_reason(i['name'],i['part'],i['url'],i['price_new'],i['price_old'],product_type=i['product_type']) is None
                                for v in selected.values() for i in v))
        self.assertTrue(all(i['availability']=='Check store' for v in selected.values() for i in v))
        self.assertEqual(sum(e['observed_price_drop'] for e in audit['price_evidence'].values()), 0)
        self.assertTrue(all(e['observations']==1 for e in audit['price_evidence'].values()))

    def test_scope_does_not_guess_from_brands_models_or_top_tubes(self):
        for name, part, kind in [
            ('SE Bikes SE RACING NARLER RETRO STEM','Steering','Stems'),
            ('Kink Backwoods Frame','Frames & Forks','Frames'),
            ('Example Frame 20.75" TT','Frames & Forks','Frames'),
            ('Example Bars Rise: 9 inches','Steering','Bars'),
            ('Example 22" Top Tube Frame','Frames & Forks','Frames')]:
            with self.subTest(name=name):self.assertIsNone(scope_reason(name,part,product_type=kind))
        self.assertIsNotNone(scope_reason('Example BMX Race Frame','Frames & Forks'))
        self.assertIsNotNone(scope_reason('Example Frame','Frames & Forks','Race-only equipment.'))
        self.assertIsNotNone(scope_reason('Example E-Bike','Bikes'))

    def test_exact_spec_fields_do_not_confuse_wheel_size_and_frame_dimensions(self):
        specs, conflicts = specifications('Frame','Frames & Forks',
            'Wheel size: 22 inches; Top tube length: 20.75 inches; Axle diameter: 14mm')
        self.assertEqual(specs, {'wheel_size_inches':['22'],'top_tube_inches':['20.75'],'axle_mm':['14']})
        self.assertEqual(conflicts, [])
        specs, _ = specifications('Cranks','Drivetrain','Crank length: 165mm')
        self.assertEqual(specs, {'crank_length_mm':['165']})
        specs, _ = specifications('Bars','Steering','Bar rise: 9 inches')
        self.assertEqual(specs, {'bar_rise_inches':['9']})

    def test_missing_ambiguous_and_conflicting_specs_are_not_fabricated(self):
        for value in ['20–22 inches','20/22 inches','20.75','unknown','20cm']:
            with self.subTest(value=value):
                specs, _ = specifications('Example','Frames & Forks', options=[('Top Tube Length',value)])
                self.assertEqual(specs,{})
        specs, conflicts = specifications('20" Wheel','Wheels',options=[('Wheel Size','22 inches')])
        self.assertNotIn('wheel_size_inches',specs)
        self.assertIn('conflicting wheel_size_inches',conflicts)
        specs, _ = specifications('Frame 22" top tube','Frames & Forks',options=[('Color','20')])
        self.assertNotIn('wheel_size_inches',specs)


class BmxAdapterTests(unittest.TestCase):
    def test_one_listing_keeps_precise_20_and_22_offers_and_variant_prices(self):
        products=json.loads((FIXTURES/'synthetic-variants.json').read_text())['products']
        parser=next(s for s in stores.scrapers() if s.part=='Wheels')
        with sports.BMX.active(), patch('stores.shopify._fetch_json',side_effect=AssertionError('no extra requests')):
            items=parser.products_from(products)
        self.assertEqual(len(items),1)
        item=items[0]
        self.assertEqual(item['url'],'https://www.albes.com/products/fixture-freestyle-wheel')
        self.assertEqual(item['price_new'],'100.00')
        self.assertEqual(item['bmx_specs']['wheel_size_inches'],['20','22'])
        self.assertEqual([v['variant_id'] for v in item['bmx_offers']],[200,220])
        self.assertEqual([v['price'] for v in item['bmx_offers']],['100','120'])
        self.assertEqual([v['availability'] for v in item['bmx_offers']],['In stock','Check store'])
        self.assertEqual(item['availability'],'Check store')
        self.assertEqual(item['price_basis'],'retailer_compare_at')

    def test_conflicting_spec_is_nonfatal_and_does_not_claim_exact_fit(self):
        product=deepcopy(json.loads((FIXTURES/'synthetic-variants.json').read_text())['products'][0])
        product['title']='20" Wheel'
        product['variants']=[product['variants'][2]]
        with sports.BMX.active():
            item=next(s for s in stores.scrapers() if s.part=='Wheels').products_from([product])[0]
        self.assertEqual(item['bmx_specs'],{})
        self.assertIn('conflicting wheel_size_inches',item['bmx_spec_warnings'])
        product['title']='Example Wheel'
        product['options']=[]
        product['variants'][0]['attributes']=['not a specification mapping']
        with sports.BMX.active():
            item=next(s for s in stores.scrapers() if s.part=='Wheels').products_from([product])[0]
        self.assertEqual(item['bmx_specs'],{})
        self.assertIn('unreadable variant specifications',item['bmx_spec_warnings'])

    def test_full_fetch_failure_is_still_a_failed_scrape_not_empty_success(self):
        parser=stores.scrapers()[0]
        with sports.BMX.active(),patch('stores.shopify.load_sale_products',return_value=None):
            self.assertIsNone(parser.scrape())


class BmxHistorySafetyTests(unittest.TestCase):
    def test_scope_changes_retain_history_without_creating_missing_products(self):
        data, history=snapshot()
        selected,audit=classify(data,history)
        old=deepcopy(history)
        excluded={i['url'] for i in audit['excluded']}
        with sports.BMX.active():
            for day in ('2026-11-02','2026-11-03'):
                record_misses(data,deepcopy(selected),history,today=day)
                pruned,stats=prune_price_history(history,today=day,current_data=selected)
                self.assertEqual(stats['dropped_filter'],0)
                self.assertEqual(set(pruned),set(history))
                apply_lifecycle(pruned,selected,today=day)
                self.assertEqual(recently_gone(pruned,selected,today=day),[])
                for url in excluded:
                    self.assertEqual(pruned[url]['prices'],old[url]['prices'])
                    self.assertNotIn('miss_streak',pruned[url])
                    self.assertEqual(pruned[url]['stage'],old[url]['stage'])

    def test_variant_only_scope_exclusion_persists_without_false_discontinuation_and_recovers(self):
        item={'name':'Example Wheel','part':'Wheels','store':"Albe's BMX",'url':'https://www.albes.com/products/example-wheel','price_new':'100','price_old':'150'}
        key="Albe's BMX_Wheels"
        history={item['url']:{**item,'prices':{'2026-11-01':100},'stage':'new'}}
        with sports.BMX.active():
            record_misses({key:[item]},{key:[]},history,today='2026-11-02',
                          scope_exclusions={item['url']:'catalog scope: no eligible 20/22-inch variants'})
            history,_=prune_price_history(history,today='2026-11-02',current_data={key:[]})
            record_misses({key:[]},{key:[]},history,today='2026-11-03')
            apply_lifecycle(history,{key:[]},today='2026-11-03')
            self.assertNotIn('miss_streak',history[item['url']])
            self.assertEqual(recently_gone(history,{key:[]},today='2026-11-03'),[])
            self.assertEqual(history[item['url']]['prices'],{'2026-11-01':100})
            from report import compare_catalogs
            self.assertEqual(compare_catalogs({key:[item]},{key:[]},excluded_urls={item['url']}),{})
            self.assertEqual(compare_catalogs({key:[item]},{key:[]})[key][0]['type'],'removed')
            record_misses({key:[]},{key:[item]},history,today='2026-11-04')
            self.assertNotIn('catalog_scope_reason',history[item['url']])

    def test_suspicious_partial_and_failed_scans_keep_existing_safeguards(self):
        data,history=snapshot()
        selected,_=classify(data,history)
        key="Albe's BMX_Wheels"
        health=empty_state()
        health['completeness_baseline']={key:[{'date':f'2026-10-{d}','count':20} for d in (28,29,30)]}
        before=deepcopy(history)
        with sports.BMX.active():
            for failed in (set(),{key}):
                result=prepare_run({key:selected[key][:1]},failed,{key:data[key]},health,today='2026-11-02')
                self.assertIn(key,result['failed_keys'])
                record_misses(data,result['current_data'],history,result['failed_keys'],today='2026-11-02')
                update_price_history(result['current_data'],history,today='2026-11-02',skip_keys=result['failed_keys'])
                self.assertEqual(history,before)
            recovered=prepare_run({key:data[key]},set(),data,empty_state(),today='2026-11-03')
            self.assertNotIn(key,recovered['failed_keys'])

    def test_compare_at_is_not_observed_history_and_skate_rules_stay_unchanged(self):
        item={'url':'https://example.test/wheel','price_new':'100','price_old':'200'}
        one={item['url']:{'prices':{'2026-11-01':100}}}
        result=price_evidence(item,one)
        self.assertEqual(result['retailer_markdown_percent'],50)
        self.assertFalse(result['observed_price_drop'])
        two={item['url']:{'prices':{'2026-10-31':120,'2026-11-01':100}}}
        self.assertTrue(price_evidence(item,two)['observed_price_drop'])
        with sports.SKATE.active():
            self.assertIsNotNone(filter_reason('Example Wheel','Wheels','https://example.test/wheel','100','200'))


class BmxPreviewTests(unittest.TestCase):
    def test_preview_rebuild_is_isolated_and_preserves_scan_and_inputs(self):
        from bs4 import BeautifulSoup
        from previews.bmx_quality import build
        from previews.shreddeals import SOURCE
        names=('previous_data.json','price_history.json','scrape_health.json','notification_state.json',
               'index.html','sale_items_chart.html','history.json','report_inputs.json')
        def hashes():
            return {n:hashlib.sha256((SOURCE/n).read_bytes()).hexdigest() if (SOURCE/n).exists() else None for n in names}
        before=hashes()
        config=deepcopy(__import__('page').ALERTS_UI_CONFIG)
        with tempfile.TemporaryDirectory() as directory, patch('urllib.request.urlopen',side_effect=AssertionError('no fetching')):
            home=build(Path(directory)/'review')
            site=home.parent
            soup=BeautifulSoup((site/'bmx/sale_items_chart.html').read_text(),'html.parser')
            self.assertEqual(len(soup.select('.deal-card')),63)
            self.assertEqual(soup.select_one('#lastScan')['datetime'],'2026-11-01T18:52:07+00:00')
            self.assertNotIn('window.SKATEDEALS_ALERTS = ',str(soup))
            self.assertNotIn('cloudflareinsights.com/beacon',str(soup))
            self.assertTrue((site/'sale_items_chart.html').is_file())
            self.assertFalse((site/'quality-audit.json').exists())
            audit=json.loads((site.parent/'quality-audit.json').read_text())
            self.assertEqual(sum(audit['after'].values()),63)
            with self.assertRaises(ValueError):build(site.parent)
        self.assertEqual(before,hashes())
        self.assertEqual(config,__import__('page').ALERTS_UI_CONFIG)


if __name__=='__main__':unittest.main()
