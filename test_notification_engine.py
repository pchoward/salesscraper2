"""Stateful watch fixtures and mocked delivery only; never use live SMTP."""
import copy
import contextlib
import io
import json
from pathlib import Path
import smtplib
import tempfile
import unittest
from unittest.mock import Mock, patch

import notification_engine as engine
from notify import deliver_digest_result
from report import Digest
from watchlist import rule_matches

FIXTURE = json.loads((Path(__file__).parent / 'tests/fixtures/notification_scenarios.json').read_text())


class NotificationEngineTests(unittest.TestCase):
    def setUp(self):
        self.item = copy.deepcopy(FIXTURE['item'])
        self.rule = copy.deepcopy(FIXTURE['threshold_rule'])
        self.smtp = patch('notify._smtp_send', side_effect=AssertionError('Live SMTP forbidden')).start()
        self.addCleanup(patch.stopall)
        self.env = {'NOTIFICATION_ENGINE_ENABLED':'1', 'NOTIFICATION_ALLOW_BOOTSTRAP':'1'}

    def plan(self, state=None, price=None, rule=None, **kwargs):
        item = dict(self.item)
        if price is not None:
            item['price_new'] = price
        return engine.evaluate(state or engine.empty_state(), [rule or self.rule], {'Zumiez_Decks':[item]}, kwargs.pop('history', {}), day=kwargs.pop('day', '2026-10-18'), **kwargs)

    def delivered(self, state):
        for event in state['events'].values():
            event['status'] = 'delivered'
        return state

    def test_fixture_threshold_reruns_and_requalification(self):
        state = engine.empty_state()
        for row in FIXTURE['prices']:
            state, hits = self.plan(state, row['price'])
            self.assertEqual(bool(hits), row['qualifies'], row)
            self.delivered(state)
        self.assertEqual(len(state['events']), 2)

    def test_zero_or_invalid_price_ceiling_does_not_become_a_default_new_match(self):
        self.assertFalse(self.plan(rule=dict(self.rule,max_price=0))[1])
        self.assertFalse(self.plan(rule=dict(self.rule,max_price=False))[1])

    def test_meaningful_drop_thresholds_and_pending_retry(self):
        rule = dict(self.rule, max_price=None, alert_on_drop=True)
        state, hits = self.plan(price='40', rule=rule)
        self.assertFalse(hits)
        state, hits = self.plan(state, '39.50', rule=rule)
        self.assertFalse(hits)
        state, hits = self.plan(state, '37.50', rule=rule)
        self.assertEqual(hits[0]['reasons'], ['Meaningful price drop'])
        ids = hits[0]['event_ids']
        state, hits = self.plan(state, '37.50', rule=rule)
        self.assertEqual(hits[0]['event_ids'], ids)
        self.delivered(state)
        state, hits = self.plan(state, '37.50', rule=rule)
        self.assertFalse(hits)
        # A smaller dollar drop still qualifies at five percent.
        state, hits = self.plan(rule=rule, price='10', previous={'Zumiez_Decks':[dict(self.item,price_new='10.60')]})
        self.assertTrue(hits)

    def test_verified_low_not_short_history_and_stable_low_does_not_repeat(self):
        rule = dict(self.rule, max_price=None, alert_on_low=True)
        history = {self.item['url']:{'first_seen':'2026-10-01','last_seen':'2026-10-18','observation_count':3,
                    'all_time_low':40,'all_time_low_date':'2026-10-18','prices':{'2026-10-01':50,'2026-10-10':45,'2026-10-18':40}}}
        state, hits = self.plan(rule=rule, history=history)
        self.assertIn('Verified historical low', hits[0]['reasons'])
        self.delivered(state)
        state, hits = self.plan(state, rule=rule, history=history)
        self.assertFalse(hits)
        short = copy.deepcopy(history); short[self.item['url']]['observation_count']=1;short[self.item['url']]['first_seen']='2026-10-18';short[self.item['url']]['prices']={'2026-10-18':40}
        self.assertFalse(self.plan(rule=rule, history=short)[1])

    def test_bad_scans_freeze_qualification_and_hold_pending_events(self):
        state, hits = self.plan()
        original = copy.deepcopy(state['records'])
        state, hits = self.plan(state, '70', failed_keys={'Zumiez_Decks'})
        self.assertFalse(hits)
        self.assertEqual(state['records'], original)
        state, hits = self.plan(state, '40')
        self.assertTrue(hits)  # original pending event is retried after a healthy recovery
        self.delivered(state)
        state, hits = self.plan(state, '70', failed_keys={'Zumiez_Decks'})
        state, hits = self.plan(state, '40')
        self.assertFalse(hits)  # a failed above-threshold scan never rearms it
        self.assertFalse(self.plan(skip_urls={self.item['url']})[1])

    def test_only_reliable_stock_transitions_alert(self):
        rule = dict(self.rule, max_price=None, alert_on_stock=True)
        self.assertFalse(self.plan(rule=rule)[1])
        self.item['stock']='out_of_stock'
        state, hits=self.plan(rule=rule)
        self.assertFalse(hits)
        self.item['stock']='in_stock'
        state, hits=self.plan(state,rule=rule)
        self.assertEqual(hits[0]['reasons'],['Back in stock (verified)'])
        self.delivered(state)
        state,hits=self.plan(state,rule=rule)
        self.assertFalse(hits)
        # Mere disappearance and reappearance is never stock evidence.
        state=engine.empty_state()
        state,_=self.plan(state,rule=rule)
        state,_=engine.evaluate(state,[rule],{'Zumiez_Decks':[]},{},day='2026-10-19')
        self.assertFalse(self.plan(state,rule=rule)[1])

    def test_sneaker_size_stock_and_product_url_rules(self):
        shoe=dict(self.item,part='Sneakers',shoe_sizes=['8','9'],shoe_prices={'8':'45','9':'60'},shoe_compares={'8':'90','9':'100'})
        rule={'product_url':shoe['url'],'part':'Sneakers','size':8,'max_price':50,'alert_on_stock':True}
        self.assertTrue(rule_matches(rule,shoe))
        self.assertFalse(rule_matches(dict(rule,size=10),shoe))
        state,hits=engine.evaluate(engine.empty_state(),[rule],{'CCS_Sneakers':[shoe]},{},day='2026-10-18')
        self.assertEqual(hits[0]['item']['price_new'],'45.00')
        self.assertEqual(hits[0]['item']['price_old'],'90.00')
        self.assertIn('Size 8',hits[0]['note'])
        self.delivered(state)
        shoe['shoe_sizes']=['9']
        state,hits=engine.evaluate(state,[rule],{'CCS_Sneakers':[shoe]},{},day='2026-10-19')
        self.assertFalse(hits)
        shoe['shoe_sizes']=['8','9']
        state,hits=engine.evaluate(state,[rule],{'CCS_Sneakers':[shoe]},{},day='2026-10-20')
        self.assertIn('Back in stock (verified)',hits[0]['reasons'])

    def test_owner_recipient_separation_and_privacy(self):
        state,hits=self.plan()
        self.assertEqual(hits[0]['owner_id'],'personal')
        self.assertEqual(hits[0]['recipient_id'],'primary')
        self.assertFalse(self.plan(state,rule=dict(self.rule,recipient_id='another'))[1])
        text=json.dumps(state)
        for sensitive in ['Baker','example.com','personal','primary','baker-under-50']:
            self.assertNotIn(sensitive,text)
        with self.assertRaises(ValueError):
            self.plan(rule=dict(self.rule,owner_id='person@example.invalid'))

    def test_retention_is_bounded_without_forgetting_active_conditions(self):
        state,_=self.plan(); self.delivered(state)
        state,hits=self.plan(state,day='2027-01-01')
        self.assertFalse(hits)
        self.assertFalse(state['events'])
        self.assertEqual(len(state['records']),1)
        with patch.object(engine,'MAX_RECORDS',1):
            self.item['url']='https://example.com/another'
            state,hits=self.plan(state)
            self.assertEqual(len(state['records']),1)
            self.assertFalse(hits)

    def test_missing_or_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; sender=Mock(return_value='sent')
            env={'NOTIFICATION_ENGINE_ENABLED':'1'}
            self.assertFalse(engine.send_notifications(Digest(),{'Zumiez_Decks':[self.item]}, {},env=env,rules=[self.rule],path=path,sender=sender))
            sender.assert_not_called()
            path.write_text('{broken')
            self.assertFalse(engine.send_notifications(Digest(),{'Zumiez_Decks':[self.item]}, {},env=self.env,rules=[self.rule],path=path,sender=sender))
            sender.assert_not_called()

    def test_definite_failure_retry_and_success_ack_survive_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; sender=Mock(side_effect=['failed','sent','empty'])
            kwargs=dict(env=self.env,rules=[self.rule],path=path,sender=sender)
            self.assertFalse(engine.send_notifications(Digest(),{'Zumiez_Decks':[self.item]}, {},**kwargs))
            self.assertEqual(next(iter(engine.load_state(path)['events'].values()))['status'],'pending')
            self.assertTrue(engine.send_notifications(Digest(),{'Zumiez_Decks':[self.item]}, {},**kwargs))
            self.assertEqual(next(iter(engine.load_state(path)['events'].values()))['status'],'delivered')
            engine.send_notifications(Digest(),{'Zumiez_Decks':[self.item]}, {},**kwargs)
            self.assertFalse(sender.call_args.args[0].watch_alerts)

    def test_uncertain_send_and_interrupted_ack_are_not_automatically_retried(self):
        for failure in ['uncertain','crash']:
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'state.json'; sender=Mock(return_value='uncertain')
                kwargs=dict(env=self.env,rules=[self.rule],path=path,sender=sender)
                if failure=='crash':
                    real_save=engine.save_state
                    calls=[]
                    def save(p,state):
                        calls.append(1)
                        if len(calls)>1:raise OSError('ack unavailable')
                        real_save(p,state)
                    sender.return_value='sent'
                    with patch.object(engine,'save_state',side_effect=save):
                        engine.send_notifications(Digest(),{'Zumiez_Decks':[self.item]}, {},**kwargs)
                else:
                    engine.send_notifications(Digest(),{'Zumiez_Decks':[self.item]}, {},**kwargs)
                engine.send_notifications(Digest(),{'Zumiez_Decks':[self.item]}, {},**kwargs)
                self.assertFalse(sender.call_args.args[0].watch_alerts)
                self.assertTrue(next(iter(engine.load_state(path)['records'].values()))['blocked'])

    def test_dry_run_does_not_ack_or_write_event_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; sender=Mock(return_value='preview')
            self.assertTrue(engine.send_notifications(Digest(),{'Zumiez_Decks':[self.item]}, {},env=self.env,rules=[self.rule],path=path,sender=sender,dry_run=True))
            self.assertFalse(path.exists())
            state,_=self.plan();engine.save_state(path,state);before=path.read_bytes()
            engine.send_notifications(Digest(),{'Zumiez_Decks':[self.item]}, {},env=self.env,rules=[self.rule],path=path,sender=sender,dry_run=True)
            self.assertEqual(path.read_bytes(),before)

    def test_unknown_size_stock_cannot_signal_a_price_or_stock_event(self):
        shoe=dict(self.item,part='Sneakers',stock='in_stock')
        rule={'product_url':shoe['url'],'part':'Sneakers','size':8,'max_price':50,'alert_on_stock':True}
        state,hits=engine.evaluate(engine.empty_state(),[rule],{'CCS_Sneakers':[shoe]},{},day='2026-10-18')
        self.assertFalse(hits)
        shoe['shoe_sizes']=['9']
        state,hits=engine.evaluate(state,[rule],{'CCS_Sneakers':[shoe]},{},day='2026-10-19')
        self.assertFalse(hits)
        shoe.pop('shoe_sizes')
        state,hits=engine.evaluate(state,[rule],{'CCS_Sneakers':[shoe]},{},day='2026-10-20')
        self.assertFalse(hits)
        shoe['shoe_sizes']=['8']
        state,hits=engine.evaluate(state,[rule],{'CCS_Sneakers':[shoe]},{},day='2026-10-21')
        self.assertIn('Back in stock (verified)',hits[0]['reasons'])

    def test_first_checkpoint_failure_prevents_email_and_other_route_notes_do_not_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            sender=Mock(return_value='sent')
            with patch.object(engine,'save_state',side_effect=OSError('disk full')):
                engine.send_notifications(Digest(),{'Zumiez_Decks':[self.item]}, {},env=self.env,rules=[self.rule],path=Path(tmp)/'state.json',sender=sender)
            sender.assert_not_called()
            digest=Digest();digest.watch_hits=[{'rule_id':'someone-else','note':'other route note','item':self.item,'reasons':[]}]
            engine.send_notifications(digest,{'Zumiez_Decks':[self.item]}, {},env=self.env,rules=[self.rule],path=Path(tmp)/'state2.json',sender=sender)
            self.assertNotIn('other route note',str(sender.call_args.args[0].watch_hits))
            self.assertEqual(digest.watch_hits[0]['note'],'other route note')

    def test_cli_resolution_is_explicit_and_never_sends(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(engine.main(['--initialize','--state',str(path)]),0)
            state,hits=self.plan()
            eid=hits[0]['event_ids'][0]
            state['events'][eid]['status']='uncertain'
            next(iter(state['records'].values()))['blocked']=True
            engine.save_state(path,state)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                engine.main(['--status','--state',str(path)])
            self.assertIn(eid,output.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):
                engine.main(['--resolve',eid,'--outcome','retry','--state',str(path)])
            restored=engine.load_state(path)
            self.assertEqual(restored['events'][eid]['status'],'pending')
            self.assertFalse(next(iter(restored['records'].values()))['blocked'])
            self.smtp.assert_not_called()

    def test_invalid_state_fields_are_not_persisted_and_cache_is_not_committed(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=engine.empty_state();state['unexpected']='private content'
            path=Path(tmp)/'state.json'
            with self.assertRaises(ValueError):engine.save_state(path,state)
            self.assertFalse(path.exists())
        workflow=Path('.github/workflows/scrape.yml').read_text()
        self.assertIn('actions/cache/restore@v4',workflow)
        self.assertIn('actions/cache/save@v4',workflow)
        self.assertIn('cancel-in-progress: false',workflow)
        git_add=next(line for line in workflow.splitlines() if 'git add ' in line)
        self.assertNotIn('notification_state.json',git_add)
        self.assertIn('notification_state.json',Path('.gitignore').read_text())

    def test_delivery_result_never_uses_live_smtp_and_distinguishes_outcomes(self):
        digest=Digest();digest.watch_alerts=[{'item':self.item,'reasons':['Maximum price reached']}]
        env={'SMTP_HOST':'smtp.example.invalid','SMTP_USER':'test','SMTP_PASSWORD':'fixture-only','EMAIL_TO':'recipient@example.invalid'}
        self.smtp.side_effect=smtplib.SMTPAuthenticationError(535,b'rejected')
        self.assertEqual(deliver_digest_result(digest,env=env),'failed')
        self.smtp.side_effect=TimeoutError('ambiguous')
        self.assertEqual(deliver_digest_result(digest,env=env),'uncertain')
        self.smtp.side_effect=None;self.smtp.return_value={}
        self.assertEqual(deliver_digest_result(digest,env=env),'sent')
        self.smtp.return_value={'recipient@example.invalid':(550,b'rejected')}
        self.assertEqual(deliver_digest_result(digest,env=env),'uncertain')
        self.assertEqual(deliver_digest_result(digest,env={}), 'skipped')
        with tempfile.TemporaryDirectory() as tmp,patch('notify.PREVIEW_PATH',str(Path(tmp)/'preview.html')):
            self.smtp.reset_mock()
            self.assertEqual(deliver_digest_result(digest,env={},dry_run=True),'preview')
            self.smtp.assert_not_called()


if __name__=='__main__':
    unittest.main()
