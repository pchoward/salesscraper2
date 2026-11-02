"""Per-sport UI contract, independent of retailer extraction changes."""
import json
from pathlib import Path
import subprocess
import unittest

import sports
from sports.facets import payload, sidebar, script


class SportFacetTests(unittest.TestCase):
    def item(self, part, specs, url='https://example.com/item'):
        return {'name': 'Fixture equipment', 'part': part, 'url': url,
                'price': '$50', 'original_price': '$100',
                'technical_offers': [
                    {'variant_id': 'a', 'price': 50, 'compare': 100, 'available': True, 'specs': specs}]}

    def test_each_sport_owns_fields_and_only_publishes_relevant_values(self):
        from unittest.mock import patch
        for sport, part, key, value, param in (
            (sports.BMX, 'Wheels', 'wheel_size', '20', 'bmx_wheel'),
            (sports.SKI, 'Skis', 'length', '172', 'ski_length'),
            (sports.MTB, 'Tires', 'tire_width', '2.4', 'mtb_tirewidth'),
        ):
            with self.subTest(sport=sport.id), patch('sports.facets.item_passes_filters', return_value=True):
                data={'fixture': [self.item(part, {key: [value]})]}
                config=payload(data, sport)
                self.assertEqual(config['fields'][0]['param'], param)
                self.assertEqual(config['items']['https://example.com/item']['part'], part)
                self.assertIn('tech-'+key, sidebar(data, lambda *a, **kw: a[2], sport))
                self.assertIn('technicalCatalog', script(data, sport))
                bad={'fixture':[self.item('Protection', {key: [value]})]}
                self.assertEqual(payload(bad, sport)['fields'], [])

    def test_same_variant_category_scope_unknown_stock_and_navigation_contract(self):
        config={'fields':[
            {'key':'length','param':'ski_length','values':['170','180'],'categories':['Skis']},
            {'key':'gender','param':'ski_gender','values':['Women'],'categories':[]},
        ],'items':{
            'ski':{'part':'Skis','offers':[
                {'price':50,'compare':100,'available':True,'specs':{'length':['170']}},
                {'price':60,'compare':120,'available':None,'specs':{'length':['180'],'gender':['Women']}},
                {'price':20,'compare':100,'available':False,'specs':{'length':['170'],'gender':['Women']}},
            ]},
            'boot':{'part':'Boots','offers':[{'price':30,'compare':60,'available':True,'specs':{}}]}
        }}
        js=r'''
const assert=require('node:assert/strict');
const f=require('./previews/sport-filters.js')(JSON.parse(process.argv[1]));
f.restore({length:'170'});assert.equal(f.allows('ski','Skis'),true);
assert.equal(f.allows('boot','Boots'),true);assert.equal(f.price('boot'),null);
assert.equal(f.allows('unknown','Skis'),false);assert.equal(f.allows('unknown','Boots'),true);
f.restore({length:'170',gender:'Women'});assert.equal(f.allows('ski','Skis'),false);
f.restore({length:'180',gender:'Women'});assert.deepEqual(f.price('ski'),{price:60,compare:120});
const p=new URLSearchParams('q=kept');f.encode(p,f.capture());assert.equal(p.get('ski_length'),'180');
assert.equal(p.get('q'),'kept');f.restore(f.decode(p));assert.equal(f.capture().length,'180');
const labels={length:{style:{}},gender:{style:{}}};
f.mount({getElementById(){return null},querySelector(s){return labels[s.includes('length')?'length':'gender']}});
f.sync('Boots');assert.equal(labels.length.hidden,true);assert.equal(labels.gender.hidden,false);
f.sync('all');assert.equal(labels.length.hidden,false);
f.clear();assert.equal(f.allows('unknown','Skis'),true);assert.equal(f.price('ski'),null);
'''
        result=subprocess.run(['node','-e',js,json.dumps(config)],cwd=Path(__file__).parent,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


class TechnicalInteractionRegressionTests(unittest.TestCase):
    def test_removable_actions_and_price_ranges_use_one_matching_variant(self):
        script = r"""
const assert=require('node:assert/strict');
const config={fields:[
 {key:'wheel',label:'Wheel size',param:'wheel',values:['29','27.5'],categories:['Forks']},
 {key:'travel',label:'Travel',param:'travel',values:['160','140'],categories:['Forks']}
],items:{fork:{part:'Forks',offers:[
 {price:100,compare:400,specs:{wheel:['27.5'],travel:['140']}},
 {price:250,compare:400,specs:{wheel:['29'],travel:['160']}},
 {price:300,compare:400,specs:{wheel:['29'],travel:['160']}},
 {price:50,compare:400,available:false,specs:{wheel:['29'],travel:['160']}}
]}}};
const f=require('./previews/sport-filters.js')(config);
f.restore({wheel:'29',travel:'160'});
assert.deepEqual(f.price('fork'),{price:250,compare:400});
assert.deepEqual(f.price('fork',undefined,{priceMin:275}),{price:300,compare:400});
assert.equal(f.allows('fork','Forks',undefined,{priceMin:275,priceMax:280}),false);
assert.equal(f.allows('missing','Forks'),false);
assert.equal(f.allows('missing','Gloves'),true);
assert.deepEqual(f.price('fork',undefined,{discountMin:30}),{price:250,compare:400});
assert.equal(f.allows('fork','Forks',undefined,{priceMin:275,discountMin:30}),false,
 'price and discount cannot match different variants');
const actions=f.actions();
assert.deepEqual(actions.map(a=>a.label),['Wheel size: 29','Travel: 160']);
assert.equal(f.price('fork',actions[0].remaining).price,250);
assert.deepEqual(f.capture(),{wheel:'29',travel:'160'},'hypothetical recovery must not mutate active state');
f.restore(actions[0].remaining);
assert.deepEqual(f.capture(),{travel:'160'});
f.clear();assert.deepEqual(f.actions(),[]);
config.items.boundary={part:'Forks',offers:[{price:70,compare:100,specs:{wheel:['29'],travel:['160']}}]};
f.restore({wheel:'29'});
assert.equal(f.allows('boundary','Forks',undefined,{discountMin:30,discountMax:30}),true,
 'an exact 30% discount must meet inclusive range boundaries');
"""
        result=subprocess.run(['node','-e',script],cwd=Path(__file__).parent,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_shell_clears_all_sport_owned_technical_query_parameters(self):
        import importlib
        from previews.shreddeals import skate_query_keys
        keys = skate_query_keys()
        for sport in sports.SPORTS.values():
            if sport.facets:
                for field in importlib.import_module(sport.facets).FIELDS:
                    self.assertIn(field['param'], keys)
        script = r"""
const assert=require('node:assert/strict'),H=require('./previews/navigation.js');
const config={defaultSport:'skate',sports:[{id:'skate',catalog:'sale_items_chart.html'},
 {id:'ski',catalog:'ski/sale_items_chart.html'},{id:'bmx',catalog:'bmx/sale_items_chart.html'}],
 skateQueryKeys:JSON.parse(process.argv[1])};
const next=H.navigate('https://example.org/?sport=ski&ski_length=170&ski_gender=Women&q=armada&utm_source=kept',config,'bmx');
assert.equal(next.searchParams.has('ski_length'),false);
assert.equal(next.searchParams.has('ski_gender'),false);
assert.equal(next.searchParams.has('q'),false);
assert.equal(next.searchParams.get('utm_source'),'kept');
"""
        result=subprocess.run(['node','-e',script,json.dumps(keys)],cwd=Path(__file__).parent,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


class VariantPriceRangeRenderingTests(unittest.TestCase):
    def test_slider_includes_available_variant_prices(self):
        from bs4 import BeautifulSoup
        from report import build_report_html
        item={'name':'UI Audit Ski','part':'Skis','store':'Fixture',
              'url':'https://example.test/ski','price_new':'100','price_old':'400',
              'technical_offers':[
                  {'price':300,'compare':400,'available':True,'specs':{'length':['170–179 cm']}},
                  {'price':999,'compare':1200,'available':False,'specs':{'length':['180–189 cm']}}]}
        with sports.SKI.active():
            html=build_report_html({'Fixture_Skis':[item]}, {}, {}, sport=sports.SKI)
        soup=BeautifulSoup(html,'html.parser')
        slider=soup.select_one('[data-min-input="priceMin"] input.dual-max')
        self.assertEqual(slider['max'], '300')


class DisappearedTechnicalFilterTests(unittest.TestCase):
    def test_gone_table_cannot_match_missing_technical_facts(self):
        source=Path(__file__).with_name('page.js').read_text()
        function=source.split('function goneRowMatches(',1)[1].split('function revealCount(',1)[0]
        script=r"""
const assert=require('node:assert/strict');
const state={search:'',store:'all',part:'all',brand:'all',priceMin:null,priceMax:null};
const typedFilters=()=>({}),typedOr=(over,typed,key,fallback)=>fallback;
const technicalPriceConstraints=()=>({}),searchHayMatches=()=>true;
const SportSpecFilters={allows:()=>false};
eval('function goneRowMatches('+JSON.parse(process.argv[1]));
assert.equal(goneRowMatches({dataset:{part:'Skis',url:'https://example.test/gone',price:'100'}}),false);
"""
        result=subprocess.run(['node','-e',script,json.dumps(function)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
