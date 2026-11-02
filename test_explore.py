"""Explore's inventory and observation boundary; no live requests."""
from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from explore.engine import available_offers, capture, identity, money
from explore.transport import Reader


def scope(sport='mtb'):
    return dict(id=sport + '-fixture', sport=sport, category='bikes' if sport == 'mtb' else 'skis',
                discipline='dirt-jump' if sport == 'mtb' else 'park', label='Fixture inventory',
                sources=[dict(id='fixture-store', base='https://example.com', collection='fixture', market='US', currency='USD',
                approved=False, product_types=['Complete Bike' if sport == 'mtb' else 'Skis'], max_pages=2,
                spec_options={'size': 'size'})])


def product(pid=1, kind='Complete Bike'):
    return dict(id=pid, handle='fixture-' + str(pid), title='Example complete', vendor='Example', product_type=kind,
                options=[{'name': 'Size', 'position': 1}], variants=[
                dict(id=pid*10, price='100.00', compare_at_price=None, available=True, option1='Small'),
                dict(id=pid*10+1, price='200.00', compare_at_price='400.00', available=True, option1='Large'),
                dict(id=pid*10+2, price='50.00', compare_at_price='100.00', available=False, option1='Medium')])


def sample(sport='mtb'):
    return capture(scope(sport), lambda *_: {'products': [product(kind='Complete Bike' if sport == 'mtb' else 'Skis')]}, '2026-11-02T12:00:00Z')


class ExploreTests(unittest.TestCase):
    def test_regular_and_sale_variants_have_distinct_observed_history(self):
        state = sample()
        small, large = available_offers(state)
        self.assertIsNone(small['compare_at'])
        self.assertEqual(large['compare_at'], '400.00')
        self.assertEqual(state['history'][large['id']]['points'][0]['price'], '200.00')
        self.assertEqual(len(state['history']), 2)
        self.assertEqual(state['history'][large['id']]['observed_high'], '200.00')
        self.assertEqual(available_offers(state, size='Large'), [large])
        self.assertEqual(available_offers(state, size='Medium'), [])
        self.assertEqual(available_offers(state, wheel_size='26'), [])

    def test_stock_unknown_is_not_confirmed_and_invalid_prices_fail_closed(self):
        p = product()
        p['variants'][0]['available'] = 'true'
        state = capture(scope(), lambda *_: {'products': [p]}, '2026-11-02T12:00:00Z')
        self.assertEqual(len(available_offers(state)), 1)
        for value in (100, 'NaN', '-1', '1.001', 'Infinity'):
            with self.assertRaises(ValueError): money(value)

    def test_complete_bikes_only_not_component_keyword_matches(self):
        state = capture(scope(), lambda *_: {'products': [product(1, 'Frames'), product(2, 'Forks'), product(3)]}, '2026-11-02T12:00:00Z')
        self.assertEqual({offer['product_id'] for offer in state['offers']}, {'3'})

    def test_failed_page_keeps_last_good_without_new_points(self):
        old = sample()
        def failed(*_): raise OSError('blocked')
        state = capture(scope(), failed, '2026-11-03T12:00:00Z', old)
        self.assertTrue(state['stale'])
        self.assertEqual(state['offers'], old['offers'])
        self.assertEqual(state['history'], old['history'])
        self.assertEqual(state['last_success'], old['last_success'])
        self.assertFalse(old['stale'])

    def test_terminal_empty_clears_current_offers_without_faking_prices(self):
        old = sample()
        state = capture(scope(), lambda *_: {'products': []}, '2026-11-03T12:00:00Z', old)
        self.assertFalse(state['stale'])
        self.assertEqual(state['offers'], [])
        self.assertEqual(state['history'], old['history'])

    def test_pagination_repeats_and_cap_fail_closed(self):
        rows = [product(i) for i in range(1,251)]
        state = capture(scope(), lambda *_: {'products': rows}, '2026-11-02T12:00:00Z')
        self.assertTrue(state['stale'])
        self.assertEqual(state['offers'], [])
        def pages(source, number, limit):
            return {'products': rows if number == 1 else []}
        self.assertFalse(capture(scope(), pages, '2026-11-02T12:00:00Z')['stale'])

    def test_partial_source_failure_does_not_publish_successful_subset(self):
        s = scope()
        second = deepcopy(s['sources'][0]); second['id'] = 'other'; second['base'] = 'https://other.example'
        s['sources'].append(second)
        def read(source, *_):
            if source['id'] == 'other': raise RuntimeError('denied')
            return {'products': [product()]}
        self.assertTrue(capture(s, read, '2026-11-02T12:00:00Z')['stale'])

    def test_market_and_currency_separate_identity_sale_and_collection_do_not(self):
        s = scope()['sources'][0]
        original = identity(s, 1, 2)
        s['collection'] = 'sale'
        self.assertEqual(identity(s, 1, 2), original)
        s['currency'] = 'CAD'
        self.assertNotEqual(identity(s, 1, 2), original)

    def test_second_sport_uses_same_engine_and_unknown_specs_stay_unknown(self):
        state = sample('ski')
        self.assertEqual({offer['sport'] for offer in state['offers']}, {'ski'})
        self.assertEqual(available_offers(state, length='178'), [])

    def test_same_day_updates_one_point_and_history_expires(self):
        old = sample()
        p = product(); p['variants'][0]['price'] = '90.00'
        state = capture(scope(), lambda *_: {'products': [p]}, '2026-11-02T20:00:00Z', old)
        small = available_offers(state, size='Small')[0]
        self.assertEqual(state['history'][small['id']]['points'], [{'day': '2026-11-02', 'price': '90.00'}])
        gone = capture(scope(), lambda *_: {'products': []}, '2027-06-01T20:00:00Z', state)
        self.assertEqual(gone['history'], {})

    def test_unapproved_source_does_not_touch_network(self):
        reader = Reader()
        with patch.object(reader, 'get', side_effect=AssertionError('network')):
            with self.assertRaisesRegex(RuntimeError, 'awaits'):
                reader(scope()['sources'][0], 1, 250)
        self.assertEqual(reader.requests, 0)

    def test_atomic_state_and_scope_guard(self):
        from explore.__main__ import save
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.json'
            state = sample(); save(path, state)
            self.assertEqual(json.loads(path.read_text()), state)
            with self.assertRaisesRegex(ValueError, 'Incompatible'):
                capture(scope('ski'), lambda *_: {}, '2026-11-02T12:00:00Z', state)

    def test_deals_sale_gate_still_excludes_regular_variant(self):
        from stores.shopify import sale_variants
        variants = sale_variants(product())
        self.assertEqual([v['id'] for v in variants], [11])

class TransportTests(unittest.TestCase):
    def approved(self):
        source = scope()['sources'][0]
        source.update(approved=True, approval_note='Fixture policy review only')
        return source

    def test_robots_denial_never_requests_feed(self):
        reader = Reader()
        with patch.object(reader, 'get', return_value=b'User-agent: *\nDisallow: /collections/') as get:
            with self.assertRaisesRegex(RuntimeError, 'robots'):
                reader(self.approved(), 1, 250)
            self.assertEqual(get.call_count, 1)

    def test_unreadable_robots_fails_closed(self):
        reader = Reader()
        with patch.object(reader, 'get', side_effect=OSError('403')) as get:
            with self.assertRaises(OSError): reader(self.approved(), 1, 250)
            self.assertEqual(get.call_count, 1)

    def test_request_budget_and_shared_url_cache(self):
        reader = Reader(max_requests=0)
        with self.assertRaisesRegex(RuntimeError, 'budget'): reader.get('https://example.com/test')
        reader.cache['https://example.com/test'] = b'cached'
        self.assertEqual(reader.get('https://example.com/test'), b'cached')

    def test_invalid_json_shape_does_not_discard_last_good(self):
        old = sample()
        for payload in ([], None, {'products': [None]}, {'products': [{'id': 1}]}):
            state = capture(scope(), lambda *_: payload, '2026-11-03T12:00:00Z', old)
            self.assertTrue(state['stale'])
            self.assertEqual(state['offers'], old['offers'])

    def test_saved_byte_metric_is_exact(self):
        from explore.__main__ import save
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'state.json'; state = sample(); save(target, state)
            self.assertEqual(state['metrics']['serialized_bytes'], target.stat().st_size)

class ExploreNavigationTests(unittest.TestCase):
    def test_optional_modes_are_isolated_and_deals_remains_default(self):
        import subprocess
        script = r'''
const assert = require('node:assert/strict');
const nav = require('./previews/navigation.js');
const config = {defaultSport:'mtb', skateQueryKeys:['q','store'], sports:[
{id:'mtb',catalog:'mtb/sale_items_chart.html'}, {id:'ski',catalog:'ski/sale_items_chart.html'}],
exploreScopes:[{id:'dj',sport:'mtb',catalog:'explore/dj/index.html'}]};
const base = 'https://example.com/?sport=mtb';
assert.equal(nav.catalogURL(base,config,'mtb').pathname,'/mtb/sale_items_chart.html');
assert.equal(nav.catalogURL(base+'&view=explore&scope=unknown',config,'mtb').pathname,'/mtb/sale_items_chart.html');
const explore = base+'&view=explore&scope=dj&ex_size=Large';
assert.equal(nav.catalogURL(explore,config,'mtb').pathname,'/explore/dj/index.html');
assert.equal(nav.catalogURL(explore,config,'mtb').search,'?ex_size=Large');
assert(!nav.navigate(explore,config,'mtb').searchParams.has('ex_size'));
const changed = nav.navigate(explore,config,'ski');
assert(!changed.searchParams.has('view')); assert(!changed.searchParams.has('scope')); assert(!changed.searchParams.has('ex_size'));
const merged = nav.mergeSkateURL(explore,'https://example.com/explore/dj/index.html?ex_brand=Example',config,'mtb');
assert.equal(merged.searchParams.get('view'),'explore'); assert(!merged.searchParams.has('ex_size'));
assert.equal(merged.searchParams.get('ex_brand'),'Example');
assert.throws(() => nav.mergeSkateURL(explore,'https://example.com/foreign',config,'mtb'));
'''
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__': unittest.main()
