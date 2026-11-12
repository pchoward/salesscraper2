"""Phone sheet presentation does not introduce another filter engine."""
import json
from pathlib import Path
import subprocess
import unittest

from report import build_report_html

ROOT = Path(__file__).resolve().parent


class PhoneFilterTests(unittest.TestCase):
    def test_top_eight_brands_use_live_counts_with_stable_ties(self):
        script = r"""
const assert=require('node:assert/strict');const {topBrands}=require('./phone-filters.js');
const rows=Array.from({length:12},(_,i)=>({key:'brand-'+i,count:i%4,order:i}));
assert.deepEqual(topBrands(rows),['brand-3','brand-7','brand-11','brand-2','brand-6','brand-10','brand-1','brand-5']);
assert.deepEqual(topBrands([{key:'none',count:0,order:0}]),[]);
assert.deepEqual(rows.map(r=>r.key),Array.from({length:12},(_,i)=>'brand-'+i),'ranking cannot mutate catalog order');
"""
        result = subprocess.run(['node','-e',script],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_report_embeds_phone_controller_without_new_filter_parameters(self):
        item={'name':'Satori Wheels 52mm Brian Delatorre Artist Conical Red Swirl',
              'part':'Wheels','store':'TGM','url':'https://example.test/wheel','price_new':20,'price_old':40}
        html=build_report_html({'TGM_Wheels':[item]},{},{},set(),generated_at='2026-11-12T00:00:00+00:00')
        self.assertIn('root.ShredPhoneFilters=api',html)
        self.assertIn('id="filterDrawer"',html)
        self.assertIn('id="brandSelect"',html)
        self.assertIn('id="clearAll"',html)
        self.assertIn('id="statusCounts"',html)
        self.assertNotIn('name="phoneFilters"',html)
        self.assertIn('@media (max-width:640px)',html)


if __name__=='__main__':unittest.main()
