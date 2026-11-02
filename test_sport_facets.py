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
