"""Owner chart provenance, native parsing, and same-offer filtering contract."""
import json
from pathlib import Path
import subprocess
import unittest

import report
from query_state import decode_query, encode_state
from truck_fit import native_size, offers_for, range_text


class TruckFitTests(unittest.TestCase):
    def test_independent_native_and_printed_axle_stay_separate(self):
        s = native_size('Independent Stage 11 159 (8.75")')
        self.assertEqual(s['native'], '159')
        self.assertEqual(s['printed_inches'], [8.75])
        self.assertEqual(s['fits'], ['8.75'])
        self.assertEqual(s['maximum'], (8.5, 9.0))
        self.assertTrue(native_size('Independent Standard 159 9.5"')['conflict'])
        self.assertFalse(native_size('Independent Standard 159 9.5"')['fits'])

    def test_family_differences_are_not_guessed(self):
        self.assertEqual(native_size('Independent Stage 4 Gonz 166')['fits'], ['8.75', '9.0'])
        self.assertFalse(native_size('Independent Stage 11 166')['fits'])
        self.assertEqual(native_size('Ace AF1 66')['fits'], ['9.0'])
        self.assertEqual(native_size('Ace Classic 66')['fits'], ['9.5+'])
        self.assertFalse(native_size('Ace 66')['fits'])
        self.assertFalse(native_size('Thunder Team 149')['fits'])
        self.assertEqual(native_size('Thunder Team 149')['native'], '149')

    def test_leading_zero_sizes_and_maximum_only(self):
        self.assertEqual(native_size('Ace Classic 00')['native'], '00')
        self.assertEqual(native_size('Ace Low 02')['native'], '02')
        s = native_size('Independent Stage 4 146')
        self.assertEqual(s['fit_basis'], 'maximum only')
        self.assertEqual(s['fits'], ['8.25', '8.5'])

    def test_af1_80_uses_owner_guidance_not_an_ideal_claim(self):
        s = native_size('Ace AF1 80')
        self.assertEqual(s['axle'], 10)
        self.assertEqual(s['hanger_mm'], 188)
        self.assertEqual(s['guidance'], (9.75, None))
        self.assertIsNone(s['ideal'])
        self.assertIsNone(s['maximum'])
        self.assertEqual(s['fits'], ['9.5+'])
        self.assertEqual(range_text(s), 'owner guidance 9.75+″')

    def test_variants_never_inherit_a_different_title_size(self):
        offers = offers_for({'name':'Ace AF1 66', 'price_new':10, 'spec_offers':[
            {'truck_size':'55','price':50,'available':True},
            {'truck_size':'66','price':80,'available':False},
            {'price':20,'available':True}]})
        self.assertEqual(offers[0]['fits'], ['8.5'])
        self.assertIs(offers[1]['available'], False)
        self.assertEqual(offers[2]['native'], '')
        self.assertFalse(offers[2]['fits'])
        self.assertEqual(offers[0]['price'], 50)
        self.assertIsNone(offers[0]['compare'])

    def test_legacy_and_new_url_filters_round_trip_separately(self):
        query = 'type=trucks&trucksize=8.75&truckfit=9.5%2B&trucknative=ace%3A80'
        state = decode_query(query)
        self.assertEqual(state['truck_sizes'], ['8.75'])
        self.assertEqual(state['truck_fit'], ['9.5+'])
        self.assertEqual(state['truck_native'], ['ace:80'])
        self.assertEqual(decode_query(encode_state(state)), state)

    def test_report_has_variant_metadata_and_exact_fit_labels(self):
        items = [{'name':'Ace AF1 80','part':'Trucks','store':'TGM',
                  'url':'https://example.test/truck/'+str(i), 'price_new':100, 'price_old':150} for i in range(5)]
        html = report.build_report_html({'TGM_Trucks':items},{},{},set(),generated_at='2026-11-07T10:00:00+00:00')
        self.assertIn('data-truck-offers=', html)
        self.assertIn('owner guidance 9.75+″', html)
        self.assertIn('data-section="truckfit" data-for="Trucks"', html)
        self.assertIn('data-section="trucknative" data-for="Trucks"', html)
        self.assertIn('data-value="ace:80"', html)

    def test_browser_independent_matching_and_search_module(self):
        subprocess.run(['node', 'test/truck-fit.test.cjs'], cwd=Path(__file__).parent, check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
